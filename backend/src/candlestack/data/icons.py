"""Instrument icons: the logo from logo.dev, kept in Redis, or one fallback image.

logo.dev (https://www.logo.dev/docs) has stock logos by ticker and crypto logos by the base
asset (``BTC`` of ``BTCUSDT``), asked with ``fallback=404`` so that a missing logo is a 404
instead of logo.dev's own monogram. Its free plan allows 500,000 requests a month, 100 a
minute and 5 at once; storing what it returns is allowed. Every logo, and every "no logo", is
fetched once and kept for days, so a page of the instrument list costs at most one request per
row the first time and none after that. Only PNG, JPEG and WebP are passed on, never SVG or
anything else from the source.

Everything that is not a logo gets the fallback: no logo at logo.dev, no key configured, or
logo.dev failing, rate limiting us or our own budget spent (then it is asked again a minute
later). The key is a query parameter, so it never goes into a log line: the URLs logged here
and by ``request_with_retry`` have no query.
"""

import asyncio
import logging
from dataclasses import dataclass
from functools import partial
from urllib.parse import quote

import httpx

from candlestack.core import RateLimiter, Settings, request_with_retry
from candlestack.data.cache import Cache
from candlestack.data.models import Instrument, Market
from candlestack.data.sources.base import DAY

logger = logging.getLogger(__name__)

TITLE = "logo.dev"
RATE_KEY = "data:rl:logodev"
# 5 requests at once is logo.dev's limit for the whole account.
CONCURRENCY = 5
LOGO_TTL = 30 * DAY
NONE_TTL = 7 * DAY
FAILED_TTL = 60
# Browser cache of a logo, of the fallback for "no logo" and of the fallback after a failure.
LOGO_MAX_AGE = DAY
NONE_MAX_AGE = 3600
FAILED_MAX_AGE = FAILED_TTL
# 128 px PNG (64 px at 2x): what a list row and the instrument page need.
QUERY = {"fallback": "404", "format": "png", "size": "64", "retina": "true"}
IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})
MAX_BYTES = 256 * 1024

# What is cached: ``<media type>\n<image>`` for a logo, or one of these.
_NONE = b"none"
_FAILED = b"failed"


@dataclass(frozen=True, slots=True)
class Icon:
    """An image to answer with, and how long a browser may keep it."""

    content: bytes
    media_type: str
    max_age: int


# The Lucide icon chart-candlestick (https://lucide.dev, ISC licence: "Copyright (c) for
# portions of Lucide are held by Cole Bemis 2013-2022 as part of Feather (MIT). All other
# copyright (c) for Lucide are held by Lucide Contributors 2022.") in white on a dark grey
# rounded square, readable in both themes.
FALLBACK_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
    b'<rect width="64" height="64" rx="14" fill="#57534e"/>'
    b'<g transform="translate(14 14) scale(1.5)" fill="none" stroke="#ffffff" stroke-width="2"'
    b' stroke-linecap="round" stroke-linejoin="round">'
    b'<path d="M9 5v4"/><rect width="4" height="6" x="7" y="9" rx="1"/><path d="M9 15v2"/>'
    b'<path d="M17 3v2"/><rect width="4" height="8" x="15" y="5" rx="1"/><path d="M17 13v3"/>'
    b'<path d="M3 3v18h18"/></g></svg>'
)
FALLBACK = Icon(FALLBACK_SVG, "image/svg+xml", NONE_MAX_AGE)
FALLBACK_AFTER_FAILURE = Icon(FALLBACK_SVG, "image/svg+xml", FAILED_MAX_AGE)


class Icons:
    """The icon of an instrument of the catalog."""

    def __init__(
        self, settings: Settings, http: httpx.AsyncClient, limiter: RateLimiter, cache: Cache
    ) -> None:
        self._url = settings.logo_dev_url.rstrip("/")
        self._key = settings.logo_dev_key.get_secret_value()
        self._limit = settings.logo_dev_rate_limit
        self._http = http
        self._limiter = limiter
        self._cache = cache
        self._calls = asyncio.Semaphore(CONCURRENCY)

    async def icon(self, instrument: Instrument) -> Icon:
        """The logo, or the fallback; never raises for the source."""
        path = logo_path(instrument)
        if not self._key or path is None:
            return FALLBACK
        blob = await self._cache.get_or_fetch(f"icon:{path}", partial(self._fetch, path))
        return decode(blob)

    async def _fetch(self, path: str) -> tuple[bytes, int]:
        wait = await self._limiter.hit(RATE_KEY, self._limit)
        if wait > 0:
            logger.warning(
                "Our %s budget (%d per minute) is spent: fallback icon for %s",
                TITLE,
                self._limit,
                path,
            )
            return _FAILED, FAILED_TTL
        async with self._calls:
            try:
                response = await request_with_retry(
                    self._http,
                    "GET",
                    f"{self._url}/{path}",
                    params={"token": self._key, **QUERY},
                    attempts=2,
                    max_delay=2.0,
                )
            except httpx.HTTPError as exc:
                logger.warning(
                    "%s could not be reached for %s (%s)", TITLE, path, type(exc).__name__
                )
                return _FAILED, FAILED_TTL
        return answer(path, response)


def logo_path(instrument: Instrument) -> str | None:
    """The logo's path at logo.dev: ``ticker/<symbol>`` for a stock, ``crypto/<base asset>``
    for a pair; ``None`` for a pair without a known base asset."""
    if instrument.market is Market.STOCK:
        return f"ticker/{quote(instrument.symbol, safe='.')}"
    if not instrument.base:
        return None
    return f"crypto/{quote(instrument.base.upper(), safe='')}"


def answer(path: str, response: httpx.Response) -> tuple[bytes, int]:
    """What to cache for logo.dev's response, and for how long."""
    status = response.status_code
    if status == 404:
        return _NONE, NONE_TTL
    if status in (401, 403):
        logger.error("%s rejected our key (HTTP %d): every icon is the fallback", TITLE, status)
        return _FAILED, FAILED_TTL
    if status != 200:
        logger.warning("%s answered HTTP %d for %s", TITLE, status, path)
        return _FAILED, FAILED_TTL
    media_type = response.headers.get("content-type", "").partition(";")[0].strip().lower()
    size = len(response.content)
    if media_type not in IMAGE_TYPES or not 0 < size <= MAX_BYTES:
        logger.warning(
            "%s sent %s (%d bytes) for %s, not an icon", TITLE, media_type or "no type", size, path
        )
        return _FAILED, FAILED_TTL
    return media_type.encode() + b"\n" + response.content, LOGO_TTL


def decode(blob: bytes) -> Icon:
    """The icon of a cached value (see ``answer``)."""
    if blob == _NONE:
        return FALLBACK
    if blob == _FAILED:
        return FALLBACK_AFTER_FAILURE
    media_type, _, content = blob.partition(b"\n")
    return Icon(content, media_type.decode(), LOGO_MAX_AGE)

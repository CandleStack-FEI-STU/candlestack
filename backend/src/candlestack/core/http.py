"""Outgoing HTTP: one shared client per app and a retry helper for flaky upstreams."""

import asyncio
import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Annotated, Any

import httpx
from fastapi import Depends, Request

from candlestack.core.config import Settings

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(10.0, connect=5.0)
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
# Failures where the request surely did not reach the upstream's application, or the
# connection dropped before any answer: safe to repeat for idempotent requests.
RETRY_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError)

# Patched by tests to avoid real waiting.
_sleep = asyncio.sleep


def create_http_client(settings: Settings) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=TIMEOUT,
        headers={"User-Agent": f"candlestack/{settings.app_version}"},
        limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
    )


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http


HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    attempts: int = 3,
    backoff: float = 0.5,
    max_delay: float = 10.0,
    **kwargs: Any,
) -> httpx.Response:
    """Sends an idempotent request, repeating it on 429, 5xx and connection errors.

    Waits `backoff` seconds, then twice as long each time, or what the upstream asks for in
    ``Retry-After``. Gives up when `attempts` are used or the wait would exceed `max_delay`:
    then the last response is returned (the caller decides what a 429 or 503 means to its
    client) or the last connection error is raised. Other responses return at once.
    """
    attempt = 1
    while True:
        try:
            response = await client.request(method, url, **kwargs)
        except RETRY_ERRORS as exc:
            if attempt >= attempts:
                raise
            delay = backoff * 2 ** (attempt - 1)
            logger.warning(
                "Retrying %s %s in %.1f s after %s", method, url, delay, type(exc).__name__
            )
        else:
            if response.status_code not in RETRY_STATUSES or attempt >= attempts:
                return response
            delay = retry_after(response)
            if delay is None:
                delay = backoff * 2 ** (attempt - 1)
            if delay > max_delay:
                return response
            await response.aclose()
            logger.warning(
                "Retrying %s %s in %.1f s after HTTP %d", method, url, delay, response.status_code
            )
        await _sleep(delay)
        attempt += 1


def retry_after(response: httpx.Response) -> float | None:
    """Seconds to wait from a ``Retry-After`` header (delay or HTTP date), if it has one."""
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - datetime.now(UTC)).total_seconds())

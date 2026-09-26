"""Alpaca, the source of the US stock market: IEX feed, paper account keys.

Intraday timeframes are built from regular-session 1m bars; 1d is Alpaca's 1Day bar, which on
IEX covers exactly the regular session, relabelled from 00:00 New York to the session open.
Trading days come from ``GET /v2/calendar``. Every request spends our budget
(``ALPACA_RATE_LIMIT``); Alpaca allows 200 per minute per key.
"""

import bisect
import logging
import time
from datetime import UTC, datetime
from typing import Any

import httpx
import orjson
import polars as pl
from anyio import to_thread

from candlestack.core import RateLimiter, Settings
from candlestack.data.cache import Cache
from candlestack.data.candles import (
    closed_only,
    normalise,
    resample_sessions,
    slice_range,
    validate,
)
from candlestack.data.errors import DataError, DataIntegrityError, InvalidRequest, SourceUnavailable
from candlestack.data.models import (
    CANDLE_SCHEMA,
    Feed,
    Instrument,
    InstrumentId,
    Market,
    Source,
    SourceHealth,
    Timeframe,
)
from candlestack.data.sessions import NEW_YORK, Session, parse_calendar
from candlestack.data.sources.base import (
    DAY,
    Period,
    get,
    json_body,
    plan_periods,
    spend,
    unavailable,
    utc,
)

logger = logging.getLogger(__name__)

NAME: Source = "alpaca"
TITLE = "Alpaca"
RATE_KEY = "data:rl:alpaca"
# adjustment=all rewrites past bars after every dividend or split, so closed periods are
# refetched daily.
CLOSED_TTL = DAY
CURRENT_TTL = DAY
CALENDAR_TTL = 7 * DAY
# How long the parsed calendar is kept in memory before Redis is asked again.
CALENDAR_MEMORY_SECONDS = 3600
HISTORY_START = 2016
BARS_LIMIT = 10_000

_COLUMNS = list(CANDLE_SCHEMA)
_BAR_SCHEMA = {
    "t": pl.String,
    "o": pl.Float64,
    "h": pl.Float64,
    "l": pl.Float64,
    "c": pl.Float64,
    "v": pl.Float64,
}


def parse_assets(content: bytes) -> list[Instrument]:
    """The tradable, non-OTC US equities (stocks and ETFs) of a ``GET /v2/assets`` body."""
    try:
        assets = [
            (item["symbol"], item.get("name") or item["symbol"], item["exchange"])
            for item in orjson.loads(content)
            if item["tradable"] and item["exchange"] != "OTC"
        ]
    except (orjson.JSONDecodeError, KeyError, TypeError) as exc:
        raise DataIntegrityError(
            f"Alpaca assets cannot be read: {type(exc).__name__} {exc}", source=NAME
        ) from None
    instruments = []
    for symbol, name, exchange in assets:
        try:
            instrument_id = InstrumentId.parse(f"stock:{symbol}")
        except InvalidRequest:
            instrument_id = None
        if instrument_id is None or instrument_id.symbol != symbol:
            logger.warning("Skipping Alpaca symbol %r: not a valid instrument symbol", symbol)
            continue
        instruments.append(
            Instrument(id=instrument_id, name=name, source=NAME, feed="iex", exchange=exchange)
        )
    return instruments


def parse_bars(bars: list[Any]) -> pl.DataFrame:
    """Bars of ``GET /v2/stocks/bars`` (``t`` RFC 3339, bar open) as candles."""
    try:
        frame = pl.from_dicts(bars, schema=_BAR_SCHEMA)
        return frame.select(
            ts=pl.col("t").str.to_datetime(time_zone="UTC").dt.epoch("s"),
            open="o",
            high="h",
            low="l",
            close="c",
            volume="v",
        )
    except (TypeError, ValueError, pl.exceptions.PolarsError) as exc:
        reason = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        raise DataIntegrityError(f"Alpaca bars cannot be read: {reason}", source=NAME) from None


def relabel_daily(frame: pl.DataFrame, sessions: list[Session]) -> pl.DataFrame:
    """1Day bars (stamped 00:00 New York) labelled with the open of that day's session; bars of
    days without a session are dropped."""
    opens = pl.DataFrame(
        {
            "date": [session.date for session in sessions],
            "open_ts": [session.open for session in sessions],
        },
        schema={"date": pl.Date, "open_ts": pl.Int64},
    )
    moment = pl.from_epoch("ts", time_unit="s").dt.replace_time_zone("UTC")
    return (
        frame.with_columns(date=moment.dt.convert_time_zone(NEW_YORK.key).dt.date())
        .join(opens, on="date", how="inner")
        .with_columns(ts="open_ts")
        .select(_COLUMNS)
        .sort("ts")
    )


def regular_candles(
    frame: pl.DataFrame, timeframe: Timeframe, period: Period, sessions: list[Session]
) -> pl.DataFrame:
    """Validated candles of the period from parsed bars (``parse_bars``): ``timeframe`` is
    ``1m`` (bars outside the regular sessions dropped) or ``1d`` (1Day bars relabelled); only
    candles closed by the end of the period."""
    if timeframe is Timeframe.D1:
        frame = relabel_daily(frame, sessions)
    frame = resample_sessions(normalise(frame), timeframe, sessions)
    frame = closed_only(
        slice_range(frame, period.start, period.end), timeframe, period.end, sessions
    )
    try:
        validate(frame)
    except DataIntegrityError as exc:
        raise DataIntegrityError(exc.detail, source=NAME) from None
    return frame


def _rfc3339(ts: int) -> str:
    return f"{utc(ts):%Y-%m-%dT%H:%M:%SZ}"


class AlpacaSource:
    name: Source = NAME
    feed: Feed = "iex"
    market = Market.STOCK
    # A chunk of 1m bars is a month, about 8000 bars parsed from JSON while it is fetched, and
    # years of them build one 1h request: few at once keep the memory of a request small.
    chunk_concurrency = 4

    def __init__(
        self, settings: Settings, http: httpx.AsyncClient, limiter: RateLimiter, cache: Cache
    ) -> None:
        self._api = settings.alpaca_api_url.rstrip("/")
        self._data = settings.alpaca_data_url.rstrip("/")
        key_id = settings.alpaca_key_id.get_secret_value()
        secret = settings.alpaca_secret_key.get_secret_value()
        self._headers = (
            {"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret}
            if key_id and secret
            else None
        )
        self._http = http
        self._limiter = limiter
        self._limit = settings.alpaca_rate_limit
        self._cache = cache
        self._sessions: list[Session] = []
        self._sessions_until = 0.0

    async def list_instruments(self) -> list[Instrument]:
        response = await self._request(
            f"{self._api}/v2/assets", {"status": "active", "asset_class": "us_equity"}
        )
        return await to_thread.run_sync(parse_assets, response.content)

    async def sessions(self) -> list[Session]:
        """NYSE sessions from 2016 to the end of next year: cached 7 days in Redis and parsed
        once an hour."""
        if time.monotonic() >= self._sessions_until:
            blob = await self._cache.get_or_fetch("calendar", self._fetch_calendar)
            self._sessions = await to_thread.run_sync(_parse_calendar, blob)
            self._sessions_until = time.monotonic() + CALENDAR_MEMORY_SECONDS
        return self._sessions

    async def first_timestamp(self, symbol: str) -> int | None:
        """Open of the session of the first 1Day bar (IEX data starts in July 2020)."""
        body = await self._bars_page(
            symbol, "1Day", {"start": f"{HISTORY_START}-01-01T00:00:00Z", "limit": 1}
        )
        frame = parse_bars(_symbol_bars(body, symbol))
        if not frame.height:
            return None
        sessions = await self.sessions()
        first = bisect.bisect_left(sessions, frame["ts"][0], key=lambda session: session.open)
        return sessions[first].open if first < len(sessions) else None

    def base_timeframe(self, timeframe: Timeframe) -> Timeframe:
        return Timeframe.D1 if timeframe is Timeframe.D1 else Timeframe.M1

    def periods(self, timeframe: Timeframe, start: int, end: int, now: int) -> list[Period]:
        # A request returns up to 10000 bars: a month of IEX 1m bars, many years of 1Day
        # bars. Whole spans keep the number of requests (our budget) small.
        return plan_periods(
            start,
            end,
            now,
            yearly=timeframe is Timeframe.D1,
            daily=False,
            closed_ttl=CLOSED_TTL,
            current_ttl=CURRENT_TTL,
        )

    async def fetch_period(self, symbol: str, timeframe: Timeframe, period: Period) -> pl.DataFrame:
        frame = await self._bars(symbol, timeframe, period.start, period.end)
        sessions = await self.sessions()
        return await to_thread.run_sync(regular_candles, frame, timeframe, period, sessions)

    async def health(self) -> SourceHealth:
        started = time.perf_counter()
        try:
            await self._request(f"{self._api}/v2/clock", {})
        except DataError as exc:
            return SourceHealth(ok=False, latency_ms=None, detail=exc.detail)
        return SourceHealth(
            ok=True, latency_ms=round((time.perf_counter() - started) * 1000), detail=None
        )

    async def _fetch_calendar(self) -> tuple[bytes, int]:
        year = datetime.now(UTC).year
        response = await self._request(
            f"{self._api}/v2/calendar",
            {"start": f"{HISTORY_START}-01-01", "end": f"{year + 1}-12-31"},
        )
        try:
            days = [
                {"date": day["date"], "open": day["open"], "close": day["close"]}
                for day in json_body(response, NAME, TITLE)
            ]
        except (KeyError, TypeError) as exc:
            raise DataIntegrityError(
                f"Alpaca calendar cannot be read: {type(exc).__name__} {exc}", source=NAME
            ) from None
        blob = orjson.dumps(days)
        await to_thread.run_sync(_parse_calendar, blob)  # never cache a calendar that fails
        return blob, CALENDAR_TTL

    async def _bars(self, symbol: str, timeframe: Timeframe, start: int, end: int) -> pl.DataFrame:
        """Every bar of ``[start, end)`` (``parse_bars``), following ``next_page_token``. Each
        page is parsed as it arrives, so the JSON objects of only one page are held at a time."""
        params: dict[str, str | int] = {
            "start": _rfc3339(start),
            "end": _rfc3339(end - 1),  # Alpaca's end is inclusive
            "limit": BARS_LIMIT,
        }
        pages = []
        while True:
            body = await self._bars_page(
                symbol, "1Day" if timeframe is Timeframe.D1 else "1Min", params
            )
            pages.append(await to_thread.run_sync(parse_bars, _symbol_bars(body, symbol)))
            token = body.get("next_page_token")
            if not token:
                return pl.concat(pages)
            params["page_token"] = token

    async def _bars_page(
        self, symbol: str, timeframe: str, params: dict[str, str | int]
    ) -> dict[str, Any]:
        response = await self._request(
            f"{self._data}/v2/stocks/bars",
            {
                **params,
                "symbols": symbol,
                "timeframe": timeframe,
                "feed": "iex",
                "adjustment": "all",
                "sort": "asc",
            },
        )
        body = json_body(response, NAME, TITLE)
        if not isinstance(body, dict):
            raise DataIntegrityError("Alpaca bars response is not an object.", source=NAME)
        return body

    async def _request(self, url: str, params: dict[str, str | int]) -> httpx.Response:
        """A request within our budget; 401/403 and other failures become ``SourceUnavailable``
        (error bodies are not trusted to be JSON: Alpaca answers 401 in HTML)."""
        if self._headers is None:
            raise SourceUnavailable(
                NAME,
                "Stock data is not available: the Alpaca keys (ALPACA_KEY_ID, "
                "ALPACA_SECRET_KEY) are not configured on this server.",
            )
        await spend(
            self._limiter,
            NAME,
            f"Alpaca request budget ({self._limit} per minute)",
            RATE_KEY,
            self._limit,
        )
        response = await get(self._http, NAME, TITLE, url, params=params, headers=self._headers)
        if response.status_code in (401, 403):
            logger.error("Alpaca rejected our API keys: HTTP %d", response.status_code)
            raise SourceUnavailable(
                NAME, "Alpaca rejected the API keys of this server. Try again later."
            )
        if response.status_code != 200:
            logger.warning(
                "Alpaca %s answered HTTP %d: %s", url, response.status_code, response.text[:200]
            )
            raise unavailable(NAME, TITLE, response)
        return response


def _symbol_bars(body: dict[str, Any], symbol: str) -> list[Any]:
    """The symbol's bars; unknown symbols come back as ``{}`` or ``null``, not as an error."""
    by_symbol = body.get("bars") or {}
    bars = (by_symbol.get(symbol) or []) if isinstance(by_symbol, dict) else None
    if not isinstance(bars, list):
        raise DataIntegrityError("Alpaca bars response has no list of bars.", source=NAME)
    return bars


def _parse_calendar(blob: bytes) -> list[Session]:
    try:
        return parse_calendar(orjson.loads(blob))
    except DataIntegrityError as exc:
        raise DataIntegrityError(exc.detail, source=NAME) from None

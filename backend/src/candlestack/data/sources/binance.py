"""Binance spot, the source of the crypto market.

Closed months come from the monthly kline archives on data.binance.vision (from the daily ones
while the monthly file is not published yet, up to 7 days after the month), the closed days of
the current month from the daily archives, and whatever has no archive yet (today, yesterday
until about 03:30 UTC) from ``GET /api/v3/klines``. Every archive is checked against its
``.CHECKSUM``. REST calls spend our weight budget (``BINANCE_WEIGHT_LIMIT``); the archives are
not limited. The 24 h stats of every pair come from one ``GET /api/v3/ticker/24hr``.
"""

import asyncio
import hashlib
import io
import logging
import time
import zipfile
from collections.abc import Sequence
from urllib.parse import quote

import httpx
import orjson
import polars as pl
from anyio import to_thread

from candlestack.core import RateLimiter, Settings, retry_after
from candlestack.data.candles import normalise, slice_range, validate
from candlestack.data.errors import DataError, DataIntegrityError, InvalidRequest, SourceUnavailable
from candlestack.data.models import (
    CANDLE_SCHEMA,
    Exchange,
    Feed,
    Instrument,
    InstrumentId,
    Market,
    Source,
    SourceHealth,
    Timeframe,
)
from candlestack.data.sessions import Session
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

NAME: Source = "binance"
TITLE = "Binance"
RATE_KEY = "data:rl:binance"
CLOSED_MONTH_TTL = 30 * DAY
CLOSED_DAY_TTL = 7 * DAY

KLINES_LIMIT = 1000
KLINES_WEIGHT = 2
EXCHANGE_INFO_WEIGHT = 20
PING_WEIGHT = 1
# GET /api/v3/ticker/24hr of every pair, without a symbol.
TICKER_WEIGHT = 80
# Volumes are in USD: a pair quoted in USDT counts as is, any other quote asset at its USDT price.
USD_QUOTE = "USDT"
# What the stats need of each pair of the 24 h ticker, which has 21 fields per pair.
_TICKER_SCHEMA = {
    "symbol": pl.String,
    "lastPrice": pl.String,
    "priceChangePercent": pl.String,
    "quoteVolume": pl.String,
}
# Binance allows 6000 weight per minute per IP, and every environment on the VM shares the IP.
# When X-MBX-USED-WEIGHT-1M reaches this, REST calls stop until the minute is over.
IP_WEIGHT_CEILING = 5000
# Open times at or above this are microseconds (archives from 2025-01-01 on), below it ms.
MICROSECONDS = 10**15
# Daily archives fetched at once when a month is built from them.
DAILY_CONCURRENCY = 16

_COLUMNS = list(CANDLE_SCHEMA)


class NotPublished(Exception):
    """The archive does not exist (yet): HTTP 404."""


def to_seconds(column: str) -> pl.Expr:
    """Epoch seconds from Binance open times in milliseconds or microseconds, per value."""
    value = pl.col(column)
    return pl.when(value >= MICROSECONDS).then(value // 1_000_000).otherwise(value // 1_000)


def parse_exchange_info(content: bytes) -> list[Instrument]:
    """The TRADING spot pairs of a ``GET /api/v3/exchangeInfo`` body, all on ``BINANCE``."""
    try:
        symbols = orjson.loads(content)["symbols"]
        pairs = [
            (item["symbol"], item["baseAsset"], item["quoteAsset"])
            for item in symbols
            if item["status"] == "TRADING"
        ]
    except (orjson.JSONDecodeError, KeyError, TypeError) as exc:
        raise DataIntegrityError(
            f"Binance exchangeInfo cannot be read: {type(exc).__name__} {exc}", source=NAME
        ) from None
    instruments = []
    for symbol, base, quote_asset in pairs:
        try:
            instrument_id = InstrumentId.parse(f"crypto:{symbol}")
        except InvalidRequest:
            instrument_id = None
        if instrument_id is None or instrument_id.symbol != symbol:
            logger.warning("Skipping Binance symbol %r: not a valid instrument symbol", symbol)
            continue
        instruments.append(
            Instrument(
                id=instrument_id,
                name=f"{base}/{quote_asset}",
                source=NAME,
                feed="spot",
                exchange=Exchange.BINANCE.value,
                base=base,
                quote=quote_asset,
            )
        )
    return instruments


def usd_prices(pairs: Sequence[tuple[str, str, float]]) -> dict[str, float]:
    """The USD price of each asset that has one, from ``(base, quote, last price)`` of the
    pairs: USDT is 1, an asset quoted in USDT its price (BTC from BTCUSDT), and an asset only
    USDT is quoted in the inverse (TRY from USDTTRY)."""
    usd = {base: price for base, quote_asset, price in pairs if quote_asset == USD_QUOTE}
    usd[USD_QUOTE] = 1.0
    for base, quote_asset, price in pairs:
        if base == USD_QUOTE:
            usd.setdefault(quote_asset, 1 / price)
    return usd


def parse_ticker(content: bytes, instruments: Sequence[Instrument]) -> pl.DataFrame:
    """The stats (``STATS_SCHEMA``) of the catalog's pairs from a ``GET /api/v3/ticker/24hr``
    body: the last price and the 24 h change as Binance reports them, and the 24 h volume in
    the quote asset converted to USD (``usd_prices``; null for a quote asset without a USD
    price). A pair without a positive last price has no stats."""
    if content.lstrip()[:1] != b"[":
        raise DataIntegrityError("Binance 24h ticker is not a list.", source=NAME)
    try:
        ticker = pl.read_json(io.BytesIO(content), schema=_TICKER_SCHEMA)
    except pl.exceptions.PolarsError as exc:
        reason = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        raise DataIntegrityError(
            f"Binance 24h ticker cannot be read: {reason}", source=NAME
        ) from None
    pairs = pl.DataFrame(
        {
            "symbol": [instrument.symbol for instrument in instruments],
            "base": [instrument.base for instrument in instruments],
            "quote": [instrument.quote for instrument in instruments],
        },
        schema={"symbol": pl.String, "base": pl.String, "quote": pl.String},
    )
    number = {
        name: pl.col(column).cast(pl.Float64, strict=False)
        for name, column in (
            ("price", "lastPrice"),
            ("change_24h", "priceChangePercent"),
            ("quote_volume", "quoteVolume"),
        )
    }
    frame = (
        pairs.join(ticker, on="symbol", how="inner")
        .with_columns(**number)
        .with_columns(
            pl.when(pl.col(name).is_finite()).then(pl.col(name)).alias(name)
            for name in ("change_24h", "quote_volume")
        )
        .filter(pl.col("price").is_finite() & (pl.col("price") > 0))
    )
    usd = usd_prices(list(frame.select("base", "quote", "price").iter_rows()))
    rate = pl.col("quote").replace_strict(usd, default=None, return_dtype=pl.Float64)
    return frame.select("symbol", "price", "change_24h", volume_24h=pl.col("quote_volume") * rate)


def parse_archive(content: bytes, name: str) -> pl.DataFrame:
    """Candles of a kline archive: a zip with one header-less CSV of 12 columns, of which open
    time, open, high, low, close and volume are used."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            csv = archive.read(archive.namelist()[0])
        frame = pl.read_csv(
            csv,
            has_header=False,
            columns=list(range(len(_COLUMNS))),
            new_columns=_COLUMNS,
            schema_overrides=CANDLE_SCHEMA,
        )
    except pl.exceptions.NoDataError:
        return pl.DataFrame(schema=CANDLE_SCHEMA)
    except (zipfile.BadZipFile, IndexError, pl.exceptions.PolarsError) as exc:
        reason = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        raise DataIntegrityError(
            f"Binance archive {name} cannot be read: {reason}", source=NAME
        ) from None
    return frame.with_columns(ts=to_seconds("ts"))


def parse_klines(rows: object, end: int | None = None) -> pl.DataFrame:
    """Candles of a ``GET /api/v3/klines`` body (times in ms); with ``end`` only those that
    closed before it (the newest row is still open when the request ran before its close)."""
    try:
        if not isinstance(rows, list):
            raise TypeError("the body is not a list")
        frame = pl.DataFrame(
            [row[:7] for row in rows],
            schema=[*_COLUMNS, "close_time"],
            orient="row",
            strict=False,
        ).cast({**CANDLE_SCHEMA, "close_time": pl.Int64})
    # KeyError: a row that is an object, not an array (slicing a dict looks the slice up).
    except (TypeError, IndexError, KeyError, pl.exceptions.PolarsError) as exc:
        reason = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        raise DataIntegrityError(f"Binance klines cannot be read: {reason}", source=NAME) from None
    if end is not None:
        frame = frame.filter(pl.col("close_time") < end * 1000)
    return frame.with_columns(ts=to_seconds("ts")).select(_COLUMNS)


def off_grid_span(frame: pl.DataFrame, timeframe: Timeframe) -> tuple[int, int] | None:
    """The bins ``[start, end)`` from the first to the last candle that does not open on the
    timeframe's UTC grid, or ``None`` when every candle does."""
    step = timeframe.seconds
    off = frame.filter(pl.col("ts") % step != 0)["ts"].sort()
    if off.is_empty():
        return None
    return off[0] // step * step, off[-1] // step * step + step


def _clean(frame: pl.DataFrame, timeframe: Timeframe, period: Period) -> pl.DataFrame:
    frame = slice_range(normalise(frame), period.start, period.end)
    try:
        validate(frame, timeframe)
    except DataIntegrityError as exc:
        raise DataIntegrityError(exc.detail, source=NAME) from None
    return frame


class BinanceSource:
    name: Source = NAME
    feed: Feed = "spot"
    market = Market.CRYPTO
    # Archives are not rate limited, and a chunk holds the requested timeframe, so a request's
    # chunks hold at most CANDLES_MAX candles in all.
    chunk_concurrency = 16

    def __init__(self, settings: Settings, http: httpx.AsyncClient, limiter: RateLimiter) -> None:
        self._api = settings.binance_api_url.rstrip("/")
        self._data = settings.binance_data_url.rstrip("/")
        self._http = http
        self._limiter = limiter
        self._weight_limit = settings.binance_weight_limit
        self._paused_until = 0.0

    async def list_instruments(self) -> list[Instrument]:
        response = await self._rest(
            "/api/v3/exchangeInfo",
            {"symbolStatus": "TRADING", "showPermissionSets": "false"},
            EXCHANGE_INFO_WEIGHT,
        )
        return await to_thread.run_sync(parse_exchange_info, response.content)

    async def sessions(self) -> list[Session] | None:
        return None

    async def first_timestamp(self, symbol: str) -> int | None:
        response = await self._rest(
            "/api/v3/klines",
            {"symbol": symbol, "interval": "1m", "startTime": 0, "limit": 1},
            KLINES_WEIGHT,
        )
        frame = parse_klines(json_body(response, NAME, TITLE))
        return frame["ts"][0] if frame.height else None

    def base_timeframe(self, timeframe: Timeframe) -> Timeframe:
        return timeframe

    # DataSource.periods: Binance chunks every timeframe alike.
    def periods(self, timeframe: Timeframe, start: int, end: int, now: int) -> list[Period]:  # noqa: ARG002
        return plan_periods(
            start,
            end,
            now,
            yearly=False,
            daily=True,
            closed_ttl=CLOSED_MONTH_TTL,
            current_ttl=CLOSED_DAY_TTL,
        )

    async def fetch_period(self, symbol: str, timeframe: Timeframe, period: Period) -> pl.DataFrame:
        if period.kind == "closed":
            frame = await self._month(symbol, timeframe, period)
        elif period.kind == "current":
            frame = await self._day(symbol, timeframe, period.start)
        else:
            frame = await self._klines(symbol, timeframe, period.start, period.end)
        return await to_thread.run_sync(_clean, frame, timeframe, period)

    async def health(self) -> SourceHealth:
        started = time.perf_counter()
        try:
            await self._rest("/api/v3/ping", {}, PING_WEIGHT)
        except DataError as exc:
            return SourceHealth(ok=False, latency_ms=None, detail=exc.detail)
        return SourceHealth(ok=True, latency_ms=_since(started), detail=None)

    async def stats(self, instruments: Sequence[Instrument]) -> pl.DataFrame:
        response = await self._rest(
            "/api/v3/ticker/24hr", {"symbolStatus": "TRADING"}, TICKER_WEIGHT
        )
        return await to_thread.run_sync(parse_ticker, response.content, instruments)

    async def _month(self, symbol: str, timeframe: Timeframe, period: Period) -> pl.DataFrame:
        try:
            return await self._archive("monthly", symbol, timeframe, period.label)
        except NotPublished:
            logger.info("No monthly archive %s %s %s yet", symbol, timeframe, period.label)
        limit = asyncio.Semaphore(DAILY_CONCURRENCY)

        async def day(start: int) -> pl.DataFrame:
            async with limit:
                return await self._day(symbol, timeframe, start)

        days = await asyncio.gather(*(day(start) for start in range(period.start, period.end, DAY)))
        return pl.concat(days)

    async def _day(self, symbol: str, timeframe: Timeframe, start: int) -> pl.DataFrame:
        label = f"{utc(start):%Y-%m-%d}"
        try:
            return await self._archive("daily", symbol, timeframe, label)
        except NotPublished:
            return await self._klines(symbol, timeframe, start, start + DAY)

    async def _archive(
        self, kind: str, symbol: str, timeframe: Timeframe, label: str
    ) -> pl.DataFrame:
        """A verified archive: ``kind`` is ``monthly`` (label ``2024-01``) or ``daily``
        (``2024-03-10``). Raises ``NotPublished`` on 404."""
        name = f"{symbol}-{timeframe}-{label}.zip"
        url = f"{self._data}/data/spot/{kind}/klines/{quote(symbol)}/{timeframe}/{quote(name)}"
        archive, checksum = await asyncio.gather(
            get(self._http, NAME, TITLE, url), get(self._http, NAME, TITLE, url + ".CHECKSUM")
        )
        for response in (archive, checksum):
            if response.status_code == 404:
                raise NotPublished(name)
            if response.status_code != 200:
                raise unavailable(NAME, f"{TITLE} archive", response)
        expected = checksum.text.split()[0].lower() if checksum.text.split() else ""
        if hashlib.sha256(archive.content).hexdigest() != expected:
            raise DataIntegrityError(
                f"Binance archive {name} does not match its published SHA-256 checksum.",
                source=NAME,
            )
        frame = await to_thread.run_sync(parse_archive, archive.content, name)
        return await self._onto_grid(symbol, timeframe, frame, name)

    async def _onto_grid(
        self, symbol: str, timeframe: Timeframe, frame: pl.DataFrame, name: str
    ) -> pl.DataFrame:
        """The archive's candles, with the span of those that open off the timeframe's UTC grid
        taken from REST instead.

        A few archives hold such candles: BTCUSDT 1m of 2017-12-04 to 12-18 opens at hh:mm:20,
        and for two days after the maintenance of 2018-02-08 the 1m to 1h candles of BTCUSDT,
        ETHUSDT and other pairs open off the grid (1h at hh:28:14). REST serves these periods on
        the grid. The span costs a few REST calls, once per cached chunk.
        """
        span = off_grid_span(frame, timeframe)
        if span is None:
            return frame
        start, end = span
        logger.warning(
            "Binance archive %s has candles off the %s grid from %s to %s: taking them from REST",
            name,
            timeframe,
            f"{utc(start):%Y-%m-%dT%H:%M}Z",
            f"{utc(end):%Y-%m-%dT%H:%M}Z",
        )
        rest = await self._klines(symbol, timeframe, start, end)
        kept = frame.filter((pl.col("ts") < start) | (pl.col("ts") >= end))
        return pl.concat([kept, rest])

    async def _klines(
        self, symbol: str, timeframe: Timeframe, start: int, end: int
    ) -> pl.DataFrame:
        """Closed candles of ``[start, end)`` from REST, 1000 per request."""
        frames = []
        cursor, last = start * 1000, end * 1000 - 1  # startTime and endTime are inclusive
        while cursor <= last:
            response = await self._rest(
                "/api/v3/klines",
                {
                    "symbol": symbol,
                    "interval": str(timeframe),
                    "startTime": cursor,
                    "endTime": last,
                    "limit": KLINES_LIMIT,
                },
                KLINES_WEIGHT,
            )
            rows = json_body(response, NAME, TITLE)
            frames.append(parse_klines(rows, end))
            if len(rows) < KLINES_LIMIT:
                break
            cursor = rows[-1][0] + 1
        return pl.concat(frames) if frames else pl.DataFrame(schema=CANDLE_SCHEMA)

    async def _rest(self, path: str, params: dict[str, str | int], weight: int) -> httpx.Response:
        """A REST call within our weight budget and Binance's per-IP limit."""
        paused = self._paused_until - time.time()
        if paused > 0:
            seconds = int(paused) + 1
            raise SourceUnavailable(
                NAME,
                f"Binance's limit for our server is reached. Try again in {seconds} seconds.",
                retry_after=seconds,
            )
        await spend(
            self._limiter,
            NAME,
            f"Binance weight budget ({self._weight_limit} per minute)",
            RATE_KEY,
            self._weight_limit,
            cost=weight,
        )
        response = await get(self._http, NAME, TITLE, self._api + path, params=params)
        self._watch_weight(response)
        if response.status_code in (418, 429):
            seconds = int(retry_after(response) or 60)
            self._pause(seconds)
            raise SourceUnavailable(
                NAME,
                f"Binance is rate limiting our requests. Try again in {seconds} seconds.",
                retry_after=seconds,
            )
        if response.status_code != 200:
            logger.warning(
                "Binance %s answered HTTP %d: %s",
                path,
                response.status_code,
                response.text[:200],
            )
            raise unavailable(NAME, TITLE, response)
        return response

    def _watch_weight(self, response: httpx.Response) -> None:
        try:
            used = int(response.headers.get("x-mbx-used-weight-1m", "0"))
        except ValueError:
            return
        if used >= IP_WEIGHT_CEILING:
            now = time.time()
            self._pause(int(60 - now % 60) + 1)
            logger.warning("Binance weight of our IP is %d this minute: pausing REST calls", used)

    def _pause(self, seconds: int) -> None:
        self._paused_until = max(self._paused_until, time.time() + seconds)


def _since(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)

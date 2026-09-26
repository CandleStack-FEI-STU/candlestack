"""Parsing of source responses and the chunk plan, on recorded responses (tests/fixtures)."""

import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from candlestack.core import RateLimiter
from candlestack.data import (
    CANDLE_SCHEMA,
    DataIntegrityError,
    Session,
    SourceUnavailable,
    Timeframe,
)
from candlestack.data.sources import base
from candlestack.data.sources.alpaca import parse_assets, parse_bars, regular_candles, relabel_daily
from candlestack.data.sources.base import DAY, Period, plan_periods, spend
from candlestack.data.sources.binance import (
    off_grid_span,
    parse_archive,
    parse_exchange_info,
    parse_klines,
    to_seconds,
)

FIXTURES = Path(__file__).parents[2] / "fixtures"
HOUR = 3600


def utc(text: str) -> int:
    return int(datetime.fromisoformat(text).replace(tzinfo=UTC).timestamp())


def fixture_bytes(path: str) -> bytes:
    return (FIXTURES / path).read_bytes()


def fixture_json(path: str) -> dict:
    return json.loads((FIXTURES / path).read_text(encoding="utf-8"))


def aapl_bars(*paths: str) -> list[dict]:
    return [bar for path in paths for bar in fixture_json(f"alpaca/{path}")["bars"]["AAPL"]]


# Binance


def test_archive_with_millisecond_open_times() -> None:
    name = "BTCUSDT-1h-2024-01.zip"

    frame = parse_archive(fixture_bytes(f"binance/archive/monthly/{name}"), name)

    assert frame.schema == CANDLE_SCHEMA
    assert frame.height == 744
    assert frame.row(0) == (utc("2024-01-01"), 42283.58, 42554.57, 42261.02, 42475.23, 1271.68108)
    assert frame["ts"][-1] == utc("2024-01-31T23:00")


def test_archive_with_microsecond_open_times() -> None:
    name = "BTCUSDT-1h-2025-01.zip"

    frame = parse_archive(fixture_bytes(f"binance/archive/monthly/{name}"), name)

    assert frame.height == 744
    assert frame.row(0) == (utc("2025-01-01"), 93576.0, 94509.42, 93489.03, 94401.14, 755.9901)
    assert frame["ts"][-1] == utc("2025-01-31T23:00")


def test_archive_with_candles_off_the_grid() -> None:
    # After the maintenance of 2018-02-08 the 1h candles open at hh:28:14 for two days.
    name = "BTCUSDT-1h-2018-02.zip"

    frame = parse_archive(fixture_bytes(f"binance/archive/monthly/{name}"), name)

    assert frame.height == 640
    assert frame.filter(pl.col("ts") % HOUR != 0)["ts"][0] == utc("2018-02-09T09:28:14")
    assert off_grid_span(frame, Timeframe.H1) == (utc("2018-02-09T09:00"), utc("2018-02-11T04:00"))


def test_archive_on_the_grid_has_no_span_to_replace() -> None:
    name = "BTCUSDT-1h-2024-01.zip"

    frame = parse_archive(fixture_bytes(f"binance/archive/monthly/{name}"), name)

    assert off_grid_span(frame, Timeframe.H1) is None
    assert off_grid_span(frame.head(0), Timeframe.H1) is None


def test_open_time_unit_is_decided_per_value() -> None:
    frame = pl.DataFrame({"t": [1735603200000, 1735689600000000, 1502928000000]})

    assert frame.select(to_seconds("t"))["t"].to_list() == [1735603200, 1735689600, 1502928000]


def test_broken_archive_is_a_data_integrity_error() -> None:
    with pytest.raises(DataIntegrityError, match=r"BTCUSDT-1h-2024-01\.zip cannot be read") as info:
        parse_archive(b"not a zip file", "BTCUSDT-1h-2024-01.zip")

    assert info.value.source == "binance"


def test_klines_are_in_seconds_and_drop_the_candle_still_open() -> None:
    rows = fixture_json("binance/rest/klines-BTCUSDT-1h-limit5.json")
    fetched_at = 1790376162  # the newest row opened at 22:00 and closes at 22:59:59.999

    frame = parse_klines(rows, end=fetched_at)

    assert frame.schema == CANDLE_SCHEMA
    assert frame["ts"].to_list() == [1790359200, 1790362800, 1790366400, 1790370000]
    assert frame.row(0)[1:] == (83785.11, 84081.41, 83785.11, 83968.0, 341.90397)
    assert parse_klines(rows).height == 5


@pytest.mark.parametrize("rows", [{"code": -1121}, [[1790359200000, "x"]], [[1, "1"] * 3]])
def test_malformed_klines_are_a_data_integrity_error(rows: object) -> None:
    with pytest.raises(DataIntegrityError, match="Binance klines cannot be read"):
        parse_klines(rows)


def test_exchange_info_lists_the_trading_pairs() -> None:
    instruments = parse_exchange_info(fixture_bytes("binance/rest/exchangeInfo-trading.json"))

    assert [str(item.id) for item in instruments] == [
        "crypto:BTCUSDT",
        "crypto:ETHUSDT",
        "crypto:SOLUSDT",
        "crypto:ETHBTC",
        "crypto:币安人生USDT",
    ]
    btc = instruments[0]
    assert (btc.name, btc.base, btc.quote, btc.source, btc.feed) == (
        "BTC/USDT",
        "BTC",
        "USDT",
        "binance",
        "spot",
    )


def test_exchange_info_skips_pairs_that_are_not_trading() -> None:
    body = {
        "symbols": [
            {"symbol": "NEOBTC", "status": "BREAK", "baseAsset": "NEO", "quoteAsset": "BTC"},
            {"symbol": "BAD-PAIR", "status": "TRADING", "baseAsset": "B", "quoteAsset": "P"},
        ]
    }

    assert parse_exchange_info(json.dumps(body).encode()) == []


# Alpaca


def test_assets_keep_tradable_stocks_outside_otc() -> None:
    instruments = parse_assets(fixture_bytes("alpaca/assets.json"))

    assert [(str(item.id), item.exchange) for item in instruments] == [
        ("stock:AAPL", "NASDAQ"),
        ("stock:SPY", "ARCA"),
        ("stock:BRK.B", "NYSE"),
    ]
    assert instruments[0].name == "Apple Inc. Common Stock"


def test_bars_of_two_pages() -> None:
    frame = parse_bars(
        aapl_bars("bars-AAPL-1Min-2024-06-03-p0.json", "bars-AAPL-1Min-2024-06-03-p1.json")
    )

    assert frame.schema == CANDLE_SCHEMA
    assert frame.height == 320
    assert frame.row(0) == (utc("2024-06-03T13:30"), 191.16, 191.47, 191.09, 191.43, 18889.0)
    assert frame["ts"][-1] == utc("2024-06-03T19:59")


def test_malformed_bars_are_a_data_integrity_error() -> None:
    with pytest.raises(DataIntegrityError, match="Alpaca bars cannot be read"):
        parse_bars([{"t": "yesterday", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}])


def test_daily_bars_are_labelled_with_the_session_open(sessions: list[Session]) -> None:
    frame = relabel_daily(
        parse_bars(
            aapl_bars("bars-AAPL-1Day-2024-06.json", "bars-AAPL-1Day-2024-11-25_12-02.json")
        ),
        sessions,
    )

    assert frame.height == 24
    assert frame["ts"][0] == utc("2024-06-03T13:30")  # 09:30 EDT
    early_close = frame.filter(pl.col("ts") == utc("2024-11-29T14:30"))  # 09:30 EST
    assert early_close.row(0)[1:] == (233.11, 236.09, 232.28, 235.68, 549571.0)


def test_daily_bars_without_a_session_are_dropped(sessions: list[Session]) -> None:
    holiday = {"t": "2024-07-04T04:00:00Z", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}

    assert relabel_daily(parse_bars([holiday]), sessions).height == 0


def test_regular_candles_drop_prints_outside_the_session(sessions: list[Session]) -> None:
    march = Period("closed", utc("2024-03-01"), utc("2024-04-01"), "2024-03", DAY)

    frame = regular_candles(
        aapl_bars("bars-AAPL-1Min-2024-03-08-open.json"), Timeframe.M1, march, sessions
    )

    assert frame.height == 62
    assert frame["ts"][0] == utc("2024-03-08T14:30")  # the 14:29 print before the open is gone


def test_regular_candles_of_the_live_tail_are_closed(sessions: list[Session]) -> None:
    live = Period("live", utc("2024-06-03"), utc("2024-06-03T14:00:30"), "2024-06-03-live", 60)
    bars = aapl_bars("bars-AAPL-1Min-2024-06-03-p0.json")

    frame = regular_candles(bars, Timeframe.M1, live, sessions)

    assert frame["ts"][-1] == utc("2024-06-03T13:59")  # 13:59 closed at 14:00, 14:00 is open


def test_regular_daily_candle_waits_for_the_close(sessions: list[Session]) -> None:
    bars = aapl_bars("bars-AAPL-1Day-2024-11-25_12-02.json")
    during = Period("live", utc("2024-11-29"), utc("2024-11-29T17:59"), "2024-11-29-live", 60)
    after = Period("live", utc("2024-11-29"), utc("2024-11-29T18:00"), "2024-11-29-live", 60)

    assert regular_candles(bars, Timeframe.D1, during, sessions).height == 0
    assert regular_candles(bars, Timeframe.D1, after, sessions)["ts"].to_list() == [
        utc("2024-11-29T14:30")
    ]


# plan_periods


def plan(start: str, end: str, now: str, **policy: bool) -> list[tuple[str, str, int, int, int]]:
    periods = plan_periods(
        utc(start),
        utc(end),
        utc(now),
        closed_ttl=30 * DAY,
        current_ttl=DAY,
        **{"yearly": False, "daily": True, **policy},
    )
    return [(p.kind, p.label, p.start, p.end, p.ttl) for p in periods]


def test_plan_closed_months_days_of_the_current_month_and_today() -> None:
    now = "2026-09-03T12:00"

    assert plan("2026-07-31T22:00", now, now) == [
        ("closed", "2026-07", utc("2026-07-01"), utc("2026-08-01"), 30 * DAY),
        ("closed", "2026-08", utc("2026-08-01"), utc("2026-09-01"), 30 * DAY),
        ("current", "2026-09-01", utc("2026-09-01"), utc("2026-09-02"), DAY),
        ("current", "2026-09-02", utc("2026-09-02"), utc("2026-09-03"), DAY),
        ("live", "2026-09-03-live", utc("2026-09-03"), utc(now), 60),
    ]


def test_plan_covers_only_what_the_request_overlaps() -> None:
    now = "2026-09-26T12:00"

    assert [p[1] for p in plan("2026-08-31T23:00", "2026-09-02T01:00", now)] == [
        "2026-08",
        "2026-09-01",
        "2026-09-02",
    ]
    assert [p[1] for p in plan("2026-09-26T01:00", "2026-09-26T02:00", now)] == ["2026-09-26-live"]


def test_plan_current_month_as_one_chunk() -> None:
    now = "2026-09-26T12:00"

    assert plan("2026-08-10", now, now, daily=False) == [
        ("closed", "2026-08", utc("2026-08-01"), utc("2026-09-01"), 30 * DAY),
        ("current", "2026-09-01..2026-09-26", utc("2026-09-01"), utc("2026-09-26"), DAY),
        ("live", "2026-09-26-live", utc("2026-09-26"), utc(now), 60),
    ]


def test_plan_years() -> None:
    now = "2026-09-26T12:00"

    assert [p[:2] for p in plan("2024-12-31", now, now, yearly=True, daily=False)] == [
        ("closed", "2024"),
        ("closed", "2025"),
        ("current", "2026-01-01..2026-09-26"),
        ("live", "2026-09-26-live"),
    ]


def test_plan_on_the_first_day_of_a_month() -> None:
    now = "2026-10-01T05:00"

    assert [p[1] for p in plan("2026-09-30", now, now)] == ["2026-09", "2026-10-01-live"]
    assert [p[1] for p in plan("2026-09-30", now, now, daily=False)] == [
        "2026-09",
        "2026-10-01-live",
    ]


# spend


class ScriptedLimiter(RateLimiter):
    """Answers hits with the given waits, without Redis."""

    def __init__(self, *waits: float) -> None:
        self.waits = list(waits)

    async def hit(self, key: str, limit: int, cost: int = 1, window: int = 60) -> float:
        return self.waits.pop(0)


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    delays: list[float] = []

    async def sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(base, "_sleep", sleep)
    return delays


@pytest.mark.anyio
async def test_spend_waits_for_the_next_window_when_it_is_near(sleeps: list[float]) -> None:
    limiter = ScriptedLimiter(3.2, 0.0)

    await spend(limiter, "alpaca", "Alpaca request budget (60 per minute)", "data:rl:alpaca", 60)

    assert sleeps == [3.2]


@pytest.mark.anyio
async def test_spend_refuses_when_the_next_window_is_far(sleeps: list[float]) -> None:
    limiter = ScriptedLimiter(42.3)

    with pytest.raises(SourceUnavailable) as info:
        await spend(limiter, "binance", "Binance weight budget (1000 per minute)", "k", 1000, 2)

    assert info.value.detail == (
        "Our Binance weight budget (1000 per minute) is spent. Try again in 43 seconds."
    )
    assert (info.value.source, info.value.retry_after) == ("binance", 43)
    assert sleeps == []

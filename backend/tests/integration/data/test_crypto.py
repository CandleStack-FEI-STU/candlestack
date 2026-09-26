"""Crypto candles through DataService: archives, REST, the cache and its failures."""

import asyncio
import json
import logging
from datetime import UTC, datetime

import httpx
import pytest

import candlestack.data.service as service_module
from candlestack.core import Settings, create_redis
from candlestack.data import (
    DataIntegrityError,
    DataService,
    InstrumentId,
    InstrumentNotFound,
    PeriodOutOfRange,
    SourceUnavailable,
    Timeframe,
    TooManyCandles,
    build_data_service,
)

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

BTC = InstrumentId.parse("crypto:BTCUSDT")
LISTED_MS = 1502942400000  # the first BTCUSDT 1m candle: 2017-08-17T04:00Z
HOUR = 3600


def utc(text: str) -> int:
    return int(datetime.fromisoformat(text).replace(tzinfo=UTC).timestamp())


def freeze(monkeypatch: pytest.MonkeyPatch, now: int) -> None:
    monkeypatch.setattr(service_module, "_time", lambda: now)


async def test_closed_month_from_its_archive_then_from_the_cache(service: DataService, upstream):
    catalog = upstream.exchange_info()
    first = upstream.first_kline(LISTED_MS)
    archive, _ = upstream.fixture_archive("monthly", "BTCUSDT-1h-2024-01.zip")

    candles = await service.candles(BTC, Timeframe.H1, utc("2024-01-01"), utc("2024-02-01"))
    again = await service.candles(BTC, Timeframe.H1, utc("2024-01-10"), utc("2024-01-11"))

    assert candles.frame.height == 744
    assert candles.frame.row(0) == (
        utc("2024-01-01"),
        42283.58,
        42554.57,
        42261.02,
        42475.23,
        1271.68108,
    )
    assert (candles.gaps, candles.gaps_total) == ([], 0)
    assert (candles.source, candles.feed) == ("binance", "spot")
    assert candles.fingerprint.startswith("sha256:")
    assert again.frame["ts"].to_list() == list(range(utc("2024-01-10"), utc("2024-01-11"), HOUR))
    assert (catalog.call_count, first.call_count, archive.call_count) == (1, 1, 1)


async def test_concurrent_requests_fetch_each_value_once(
    service: DataService, upstream, settings: Settings, redis, http: httpx.AsyncClient
):
    other_process = build_data_service(settings, redis, http)
    catalog = upstream.exchange_info()
    first = upstream.first_kline(LISTED_MS)
    archive, _ = upstream.fixture_archive("monthly", "BTCUSDT-1h-2024-01.zip")

    results = await asyncio.gather(
        *(
            each.candles(BTC, Timeframe.H1, utc("2024-01-01"), utc("2024-02-01"))
            for each in [service, other_process] * 3
        )
    )

    assert {result.fingerprint for result in results} == {results[0].fingerprint}
    assert (catalog.call_count, first.call_count, archive.call_count) == (1, 1, 1)


async def test_month_boundary_and_the_current_month(
    service: DataService, upstream, monkeypatch: pytest.MonkeyPatch
):
    now = utc("2025-02-03T02:30")
    freeze(monkeypatch, now)
    upstream.exchange_info()
    upstream.first_kline(LISTED_MS)
    upstream.fixture_archive("monthly", "BTCUSDT-1h-2025-01.zip")  # microsecond times
    name = "BTCUSDT-1h-2025-02-01.zip"
    opens = [(utc("2025-02-01") + hour * HOUR) * 10**6 for hour in range(24)]
    upstream.archive("daily", name, upstream.make_archive(name, opens, HOUR * 10**6))
    upstream.archive("daily", "BTCUSDT-1h-2025-02-02.zip", None)  # not published yet
    yesterday = upstream.klines(
        utc("2025-02-02") * 1000,
        [upstream.kline((utc("2025-02-02") + hour * HOUR) * 1000) for hour in range(24)],
    )
    today = upstream.klines(  # the 02:00 candle is still open at 02:30
        utc("2025-02-03") * 1000,
        [upstream.kline((utc("2025-02-03") + hour * HOUR) * 1000) for hour in range(3)],
    )

    candles = await service.candles(BTC, Timeframe.H1, utc("2025-01-31T20:00"), now)

    assert candles.frame["ts"].to_list() == list(
        range(utc("2025-01-31T20:00"), utc("2025-02-03T02:00"), HOUR)
    )
    assert candles.gaps_total == 0
    assert yesterday.calls.last.request.url.params["endTime"] == str(utc("2025-02-03") * 1000 - 1)
    assert today.calls.last.request.url.params["endTime"] == str(now * 1000 - 1)


async def test_month_without_its_archive_is_built_from_daily_ones(
    service: DataService, upstream, monkeypatch: pytest.MonkeyPatch
):
    freeze(monkeypatch, utc("2024-04-02T12:00"))  # the monthly archive of March is not out yet
    upstream.exchange_info()
    upstream.first_kline(LISTED_MS)
    monthly, _ = upstream.archive("monthly", "BTCUSDT-1h-2024-03.zip", None)
    daily = []
    for day in range(1, 32):
        name = f"BTCUSDT-1h-2024-03-{day:02}.zip"
        if day == 10:
            daily.append(upstream.fixture_archive("daily", name))
        else:
            opens = [(utc(f"2024-03-{day:02}") + hour * HOUR) * 1000 for hour in range(24)]
            daily.append(
                upstream.archive("daily", name, upstream.make_archive(name, opens, HOUR * 1000))
            )

    candles = await service.candles(BTC, Timeframe.H1, utc("2024-03-09"), utc("2024-03-11"))

    assert candles.frame["ts"].to_list() == list(range(utc("2024-03-09"), utc("2024-03-11"), HOUR))
    assert candles.frame.row(24) == (
        utc("2024-03-10"),
        68313.28,
        68449.18,
        68200.0,
        68343.12,
        1024.01076,
    )
    assert monthly.call_count == 1
    assert all(zip_route.call_count == 1 for zip_route, _ in daily)


async def test_archive_candles_off_the_grid_are_taken_from_rest(service: DataService, upstream):
    # The 2018-02 archive has 1h candles at hh:28:14 from 02-09T09:28:14 to 02-11T03:28:14;
    # REST has that span on the grid, from 02-09T10:00.
    upstream.exchange_info()
    upstream.first_kline(LISTED_MS)
    archive, _ = upstream.fixture_archive("monthly", "BTCUSDT-1h-2018-02.zip")
    rest = upstream.klines(
        utc("2018-02-09T09:00") * 1000,
        json.loads(
            upstream.fixture_bytes("binance/rest/klines-BTCUSDT-1h-2018-02-09-maintenance.json")
        ),
    )

    candles = await service.candles(BTC, Timeframe.H1, utc("2018-02-07"), utc("2018-02-11"))
    again = await service.candles(BTC, Timeframe.H1, utc("2018-02-09"), utc("2018-02-10"))

    opens = candles.frame["ts"].to_list()
    assert [t for t in opens if t % HOUR] == []
    assert (len(opens), candles.gaps_total) == (63, 33)  # 96 bins, the maintenance is the gap
    assert candles.gaps == [(utc("2018-02-08T01:00"), utc("2018-02-09T10:00"))]
    assert candles.frame.row(opens.index(utc("2018-02-09T10:00"))) == (
        utc("2018-02-09T10:00"),
        7789.9,
        8390.0,
        7789.9,
        8269.84,
        2131.59828,
    )
    assert again.frame.height == 14
    assert rest.calls.last.request.url.params["endTime"] == str(utc("2018-02-11T04:00") * 1000 - 1)
    assert (archive.call_count, rest.call_count) == (1, 1)  # the repaired month is cached


async def test_archive_with_a_wrong_checksum_is_never_cached(service: DataService, upstream):
    upstream.exchange_info()
    upstream.first_kline(LISTED_MS)
    name = "BTCUSDT-1h-2024-01.zip"
    archive, _ = upstream.archive(
        "monthly",
        name,
        upstream.fixture_bytes(f"binance/archive/monthly/{name}"),
        upstream.checksum(b"something else", name),
    )

    for _ in range(2):
        with pytest.raises(DataIntegrityError, match="does not match its published") as info:
            await service.candles(BTC, Timeframe.H1, utc("2024-01-01"), utc("2024-02-01"))
        assert info.value.source == "binance"

    assert archive.call_count == 2


async def test_rate_limit_of_binance_pauses_rest_calls(
    service: DataService, upstream, monkeypatch: pytest.MonkeyPatch
):
    now = utc("2025-02-03T02:30")
    freeze(monkeypatch, now)
    upstream.exchange_info()
    upstream.first_kline(LISTED_MS)
    today = upstream.router.get(
        f"{upstream.BINANCE_API}/api/v3/klines",
        params={"startTime": str(utc("2025-02-03") * 1000)},
    ).respond(429, headers={"Retry-After": "30"})

    for _ in range(2):
        with pytest.raises(SourceUnavailable) as info:
            await service.candles(BTC, Timeframe.H1, utc("2025-02-03"), now)
        assert info.value.retry_after in (29, 30)
        assert info.value.source == "binance"

    assert today.call_count == 1  # the second request did not reach Binance


async def test_works_without_redis(
    settings: Settings, http: httpx.AsyncClient, upstream, caplog: pytest.LogCaptureFixture
):
    dead_redis = create_redis("redis://127.0.0.1:1/0")
    service = build_data_service(settings, dead_redis, http)
    upstream.exchange_info()
    upstream.first_kline(LISTED_MS)
    archive, _ = upstream.fixture_archive("monthly", "BTCUSDT-1h-2024-01.zip")

    with caplog.at_level(logging.WARNING):
        for _ in range(2):
            candles = await service.candles(BTC, Timeframe.H1, utc("2024-01-01"), utc("2024-02-01"))
            assert candles.frame.height == 744
    await dead_redis.aclose()

    assert archive.call_count == 2  # nothing was cached
    assert "working without the cache" in caplog.text


async def test_checks_before_any_candle_is_fetched(service: DataService, upstream):
    upstream.exchange_info()
    upstream.first_kline(LISTED_MS)

    with pytest.raises(InstrumentNotFound):
        await service.candles(InstrumentId.parse("crypto:NOPEUSDT"), Timeframe.H1, 0, 3600)
    with pytest.raises(PeriodOutOfRange, match="from 2017-08-17T04:00:00Z") as early:
        await service.candles(BTC, Timeframe.H1, utc("2017-08-17T03:00"), utc("2017-08-18"))
    with pytest.raises(PeriodOutOfRange, match="Set end to") as late:
        await service.candles(BTC, Timeframe.H1, utc("2024-01-01"), utc("2100-01-01"))
    with pytest.raises(TooManyCandles, match="Use 5m or a larger timeframe") as many:
        await service.candles(BTC, Timeframe.M1, utc("2024-01-01"), utc("2024-04-01"))

    assert early.value.available_from == utc("2017-08-17T04:00")
    assert late.value.available_to <= utc("2100-01-01")
    assert (many.value.requested, many.value.maximum) == (131040, 50000)
    # The first 1d candle opens at 00:00, before the first trade.
    with pytest.raises(PeriodOutOfRange) as daily:
        await service.candles(BTC, Timeframe.D1, utc("2017-08-16"), utc("2017-08-18"))
    assert daily.value.available_from == utc("2017-08-17")


async def test_instrument_info(service: DataService, upstream, monkeypatch: pytest.MonkeyPatch):
    freeze(monkeypatch, utc("2026-09-26T12:34:56"))
    upstream.exchange_info()
    upstream.first_kline(LISTED_MS)

    info = await service.instrument(BTC)

    assert str(info.instrument.id) == "crypto:BTCUSDT"
    assert info.timeframes == tuple(Timeframe)
    assert (info.available_from, info.available_to) == (
        utc("2017-08-17T04:00"),
        utc("2026-09-26T12:33"),
    )
    assert info.max_candles == 50000

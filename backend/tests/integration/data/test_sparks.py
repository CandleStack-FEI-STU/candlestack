"""The daily candles of the mini charts: fetched from both sources (mocked with respx) once a day,
kept in a real Redis, and carried by the instrument list."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis

from candlestack.core import Settings
from candlestack.data import (
    DataService,
    Market,
    SearchResult,
    build_data_service,
    stats_store,
)
from candlestack.data import service as service_module
from candlestack.data.sources import alpaca, base, binance
from candlestack.data.spark_store import (
    GRACE_SECONDS,
    RETRY_SECONDS,
    SETTLE_SECONDS,
    SparkStore,
)

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

DAY = 86_400
# A Saturday: crypto's last daily candle closed at 00:00 UTC, the stocks' with Friday's session.
NOW = int(datetime(2024, 11, 16, 12, tzinfo=UTC).timestamp())
CRYPTO_DAYS = [NOW // DAY * DAY - (10 - i) * DAY for i in range(10)]  # 11-06 to 11-15
# The last 10 sessions (11-04 to 11-15, 14:30 UTC in winter), and the bars' stamps of their days.
STOCK_DATES = ["04", "05", "06", "07", "08", "11", "12", "13", "14", "15"]
STOCK_DAYS = [int(datetime(2024, 11, int(d), 14, 30, tzinfo=UTC).timestamp()) for d in STOCK_DATES]


class Clock:
    """The service's and the stores' wall clock, moved by the tests."""

    def __init__(self) -> None:
        self.now = float(NOW)

    def __call__(self) -> float:
        return self.now


@pytest.fixture(autouse=True)
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    clock = Clock()
    monkeypatch.setattr(service_module, "_time", clock)
    monkeypatch.setattr(stats_store, "_time", clock)
    return clock


def sparks(found: SearchResult) -> dict[str, Any]:
    return {str(item.id): spark for item, spark in zip(found.items, found.sparks, strict=True)}


def price(symbol: str, day: int) -> float:
    return 100.0 + len(symbol) + day % (30 * DAY) / DAY


class Sources:
    """The klines and daily bars routes; ``down`` and ``missing`` change their answers."""

    def __init__(self, upstream) -> None:
        upstream.exchange_info()
        upstream.assets()
        upstream.calendar()
        # Symbol -> HTTP status answered instead of candles; 200 is a body that is no list.
        self.down: dict[str, int] = {"ETHBTC": 400}
        # Symbol -> days without a candle.
        self.missing: dict[str, set[int]] = {
            "ETHUSDT": {CRYPTO_DAYS[4]},
            "币安人生USDT": set(CRYPTO_DAYS[:7]),  # listed three days ago
            "SPY": {STOCK_DAYS[0]},
            "BRK.B": set(STOCK_DAYS),
        }
        self.pages: list[str] = []
        self.klines = upstream.router.get(
            f"{upstream.BINANCE_API}/api/v3/klines", params={"interval": "1d"}
        ).mock(side_effect=self._klines)
        self.bars = upstream.router.get(
            f"{upstream.ALPACA_DATA}/v2/stocks/bars", params={"timeframe": "1Day"}
        ).mock(side_effect=self._bars)
        self.kline = upstream.kline

    def _klines(self, request: httpx.Request) -> httpx.Response:
        symbol, params = request.url.params["symbol"], request.url.params
        if symbol in self.down:
            return httpx.Response(self.down[symbol], json={"code": -1121})
        start, end = int(params["startTime"]) // 1000, int(params["endTime"]) // 1000
        assert int(params["limit"]) == 10
        rows = [
            self.kline(day * 1000, DAY * 1000, price(symbol, day))
            for day in range(start, end, DAY)
            if day not in self.missing.get(symbol, ())
        ]
        return httpx.Response(200, json=rows)

    def _bars(self, request: httpx.Request) -> httpx.Response:
        params = request.url.params
        if "BRK.B" in self.down:
            return httpx.Response(self.down["BRK.B"], json={"message": "down"})
        assert (params["start"], params["end"]) == ("2024-11-04T00:00:00Z", "2024-11-15T20:59:59Z")
        bars = {
            symbol: [
                {
                    # 00:00 New York, as Alpaca stamps a daily bar.
                    "t": f"{datetime.fromtimestamp(day, UTC):%Y-%m-%d}T05:00:00Z",
                    "o": price(symbol, day),
                    "h": price(symbol, day) + 2,
                    "l": price(symbol, day) - 2,
                    "c": price(symbol, day) + 1,
                    "v": 1000,
                }
                for day in STOCK_DAYS
                if day not in self.missing.get(symbol, ())
            ]
            for symbol in params["symbols"].split(",")
        }
        self.pages.append(params.get("page_token", ""))
        return httpx.Response(200, json={"bars": bars, "next_page_token": None})


@pytest.fixture
def sources(upstream) -> Sources:
    return Sources(upstream)


async def test_the_list_carries_the_last_daily_candles(
    service: DataService, sources: Sources, caplog
):
    sources.down["SOLUSDT"] = 503

    with caplog.at_level(logging.INFO):
        await service.refresh_daily_candles()
    found = sparks(await service.search(None, limit=100))

    btc = found["crypto:BTCUSDT"]
    assert [candle[0] for candle in btc] == CRYPTO_DAYS
    first = price("BTCUSDT", CRYPTO_DAYS[0])
    assert btc[0] == (CRYPTO_DAYS[0], first, first + 1, first - 1, first + 0.5)
    assert found["crypto:ETHUSDT"][4] is None  # a day without a candle is a gap
    assert sum(candle is None for candle in found["crypto:ETHUSDT"]) == 1
    assert found["crypto:币安人生USDT"][:7] == [None] * 7
    assert found["crypto:SOLUSDT"] is None  # failed twice, nothing to keep
    assert found["crypto:ETHBTC"] is None  # refused
    aapl = found["stock:AAPL"]
    assert [candle[0] for candle in aapl] == STOCK_DAYS
    assert aapl[-1][1:] == (
        price("AAPL", STOCK_DAYS[-1]),
        price("AAPL", STOCK_DAYS[-1]) + 2,
        price("AAPL", STOCK_DAYS[-1]) - 2,
        price("AAPL", STOCK_DAYS[-1]) + 1,
    )
    assert found["stock:SPY"][0] is None
    assert found["stock:BRK.B"] is None
    assert "Binance refused the daily candles of ETHBTC: none for them" in caplog.text
    assert "Binance daily candles of 1 of 5 pairs failed" in caplog.text
    assert "Refreshed the stock spark: 19 rows" in caplog.text
    assert sources.bars.call_count == 1


async def test_daily_candles_are_fetched_once_a_day(
    service: DataService, sources: Sources, clock: Clock
):
    await service.refresh_daily_candles()
    clock.now += 6 * 3600  # Saturday evening: no new daily close
    await service.refresh_daily_candles()
    assert (sources.klines.call_count, sources.bars.call_count) == (5, 1)

    clock.now = NOW // DAY * DAY + DAY + 600  # 00:10 UTC: the new candle settles at 00:15
    await service.refresh_daily_candles()
    assert sources.klines.call_count == 5

    clock.now += 300
    await service.refresh_daily_candles()
    assert (sources.klines.call_count, sources.bars.call_count) == (10, 1)  # stocks: weekend
    found = sparks(await service.search(None, Market.CRYPTO))
    assert found["crypto:BTCUSDT"][-1][0] == NOW // DAY * DAY


async def test_a_pair_that_fails_keeps_its_last_candles(
    service: DataService, sources: Sources, clock: Clock, caplog
):
    await service.refresh_daily_candles()
    clock.now += DAY
    sources.down["BTCUSDT"] = 503

    with caplog.at_level(logging.WARNING):
        await service.refresh_daily_candles()
    btc = sparks(await service.search(None, Market.CRYPTO))["crypto:BTCUSDT"]

    # Yesterday's candles in today's days: the newest day is a gap.
    assert [candle and candle[0] for candle in btc] == [*CRYPTO_DAYS[1:], None]
    assert "Binance daily candles of 1 of 5 pairs failed" in caplog.text

    # Shown until 12 hours after the next daily close settled: Sunday 12:15 UTC.
    clock.now = NOW // DAY * DAY + DAY + SETTLE_SECONDS + GRACE_SECONDS
    found = sparks(await service.search(None, Market.CRYPTO))
    assert found["crypto:BTCUSDT"] is None
    assert found["crypto:ETHUSDT"] is not None


async def test_when_binance_is_down_the_last_candles_stay_and_the_next_try_waits(
    service: DataService, sources: Sources, clock: Clock, monkeypatch: pytest.MonkeyPatch, caplog
):
    await service.refresh_daily_candles()
    before = sparks(await service.search(None, Market.CRYPTO))
    clock.now += DAY
    monkeypatch.setattr(binance, "SPARK_FAILURES_IN_A_ROW", 2)
    sources.down.update(dict.fromkeys(["BTCUSDT", "ETHUSDT", "SOLUSDT", "币安人生USDT"], 200))
    calls = sources.klines.call_count

    with caplog.at_level(logging.WARNING):
        await service.refresh_daily_candles()

    # Two failures in a row stop a round: two rounds of two requests.
    assert sources.klines.call_count - calls == 4
    assert "Refreshing the crypto spark failed: Binance klines cannot be read" in caplog.text
    assert sparks(await service.search(None, Market.CRYPTO)) == before

    await service.refresh_daily_candles()
    assert sources.klines.call_count - calls == 4  # waits RETRY_SECONDS

    clock.now += RETRY_SECONDS
    sources.down = {}
    await service.refresh_daily_candles()
    found = sparks(await service.search(None, Market.CRYPTO))
    assert found["crypto:BTCUSDT"][-1][0] == NOW // DAY * DAY


async def test_another_process_adopts_the_candles_from_redis(
    service: DataService, sources: Sources
):
    await service.refresh_daily_candles()
    found = await service.search(None, limit=100)

    other = SparkStore(service._cache, [Market.CRYPTO, Market.STOCK])
    assert await other.sparks(found.items) == found.sparks
    assert await other.sparks([]) == []


async def test_without_candles_the_list_has_no_mini_charts(service: DataService, upstream):
    upstream.exchange_info()
    upstream.assets()

    found = await service.search(None, limit=100)

    assert found.sparks == [None] * len(found.items)


async def test_daily_candles_are_paced_to_their_share_of_the_budget(
    settings: Settings,
    redis: Redis,
    http: httpx.AsyncClient,
    sources: Sources,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(binance, "SPARK_WEIGHT_SHARE_MAX", 4)  # two klines requests a minute
    service = build_data_service(settings, redis, http)
    waited = []

    async def sleep(seconds: float) -> None:
        waited.append(seconds)
        await redis.delete(*await redis.keys("data:rl:binance-spark:*"))  # the next minute

    monkeypatch.setattr(base, "_sleep", sleep)
    await service.refresh_daily_candles()

    assert sources.klines.call_count == 5
    assert len(waited) == 2
    assert all(0 < seconds <= 60 for seconds in waited)


async def test_alpaca_daily_bars_follow_the_pages_and_split_into_batches(
    service: DataService, sources: Sources, upstream, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(alpaca, "SNAPSHOT_SYMBOLS", 2)  # AAPL and SPY, then BRK.B
    answer = sources._bars
    pages = iter(["next", None])

    def paged(request: httpx.Request) -> httpx.Response:
        response = answer(request)
        if "page_token" in request.url.params or "BRK.B" in request.url.params["symbols"]:
            return response
        body = response.json()
        body["next_page_token"] = next(pages)
        return httpx.Response(200, json=body)

    sources.bars.side_effect = paged

    await service.refresh_daily_candles()
    found = sparks(await service.search(None, Market.STOCK))

    assert sources.pages == ["", "next", ""]
    assert found["stock:AAPL"] is not None


async def test_when_alpaca_is_down_the_stocks_have_no_candles_yet(
    service: DataService, sources: Sources, caplog
):
    sources.down["BRK.B"] = 503

    with caplog.at_level(logging.WARNING):
        await service.refresh_daily_candles()

    assert "Refreshing the stock spark failed: Alpaca failed with HTTP 503" in caplog.text
    assert sparks(await service.search(None, Market.STOCK)) == dict.fromkeys(
        ["stock:SPY", "stock:AAPL", "stock:BRK.B"]
    )


async def test_an_unexpected_failure_of_one_market_does_not_stop_the_other(
    service: DataService, sources: Sources, monkeypatch: pytest.MonkeyPatch, caplog
):
    async def broken(_instruments, _closed_at):
        raise RuntimeError("boom")

    monkeypatch.setattr(service._sources[Market.CRYPTO], "daily_candles", broken)
    with caplog.at_level(logging.ERROR):
        await service.refresh_daily_candles()

    assert "Refreshing the crypto daily candles failed" in caplog.text
    assert sources.bars.call_count == 1


async def test_no_stock_session_yet_asks_for_nothing(
    service: DataService, sources: Sources, clock: Clock
):
    clock.now = datetime(2016, 1, 1, tzinfo=UTC).timestamp()  # before the calendar

    await service.refresh_daily_candles()

    assert sources.bars.call_count == 0


async def test_no_closed_session_in_the_calendar_gives_no_stock_candles(
    service: DataService, sources: Sources
):
    source = service._sources[Market.STOCK]
    sessions = await source.sessions()
    assert sessions

    found = await source.daily_candles([], sessions[0].open)

    assert found.frame.height == 0


async def test_keep_stats_fresh_runs_both_refreshes_until_cancelled(
    service: DataService, monkeypatch: pytest.MonkeyPatch
):
    rounds: dict[str, int] = {"stats": 0, "daily": 0}

    def counting(name: str):
        async def refresh() -> None:
            rounds[name] += 1

        return refresh

    async def sleep(seconds: float) -> None:
        assert seconds == service_module.STATS_CHECK_SECONDS
        if min(rounds.values()) >= 3:
            raise asyncio.CancelledError
        await asyncio.sleep(0)

    monkeypatch.setattr(service, "refresh_stats", counting("stats"))
    monkeypatch.setattr(service, "refresh_daily_candles", counting("daily"))
    monkeypatch.setattr(base, "_sleep", sleep)

    await asyncio.wait_for(service.keep_stats_fresh(), 5)

    assert min(rounds.values()) >= 3


async def one_tick(service: DataService, monkeypatch: pytest.MonkeyPatch) -> None:
    """One round of ``keep_stats_fresh`` (without the stats): each loop stops at its first
    wait."""

    async def nothing() -> None:
        pass

    async def stop(_seconds: float) -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr(service, "refresh_stats", nothing)
    monkeypatch.setattr(base, "_sleep", stop)
    await asyncio.wait_for(service.keep_stats_fresh(), 5)


async def test_without_stored_candles_the_first_tick_refreshes_at_once(
    service: DataService, sources: Sources, clock: Clock, monkeypatch: pytest.MonkeyPatch
):
    clock.now = NOW // DAY * DAY + 6 * 3600  # 06:00 UTC, long after the daily slot

    await one_tick(service, monkeypatch)

    assert (sources.klines.call_count, sources.bars.call_count) == (5, 1)
    assert sparks(await service.search(None, Market.CRYPTO))["crypto:BTCUSDT"] is not None


async def test_with_fresh_candles_the_tick_waits_for_the_daily_slot(
    service: DataService,
    sources: Sources,
    clock: Clock,
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    redis: Redis,
    http: httpx.AsyncClient,
):
    await service.refresh_daily_candles()
    other = build_data_service(settings, redis, http)

    clock.now += 6 * 3600
    await one_tick(other, monkeypatch)  # another process: adopts them from Redis
    assert (sources.klines.call_count, sources.bars.call_count) == (5, 1)

    clock.now = NOW // DAY * DAY + DAY + SETTLE_SECONDS  # crypto's next slot
    await one_tick(other, monkeypatch)
    assert (sources.klines.call_count, sources.bars.call_count) == (10, 1)


async def test_stock_candles_are_shown_until_after_the_next_session(
    service: DataService, sources: Sources, clock: Clock
):
    await service.refresh_daily_candles()  # Saturday: the candles up to Friday's session

    # Monday's session closes at 21:00 UTC: they stay through the weekend and until 12 hours
    # after Monday's candle settled, and are not fetched again before.
    monday = int(datetime(2024, 11, 18, 21, tzinfo=UTC).timestamp()) + SETTLE_SECONDS
    clock.now = monday - 1
    await service.refresh_daily_candles()
    assert sources.bars.call_count == 1
    clock.now = monday + GRACE_SECONDS - 1
    assert sparks(await service.search(None, Market.STOCK))["stock:AAPL"] is not None
    clock.now += 1
    assert sparks(await service.search(None, Market.STOCK))["stock:AAPL"] is None


async def test_unanswered_pairs_are_asked_again_until_the_next_daily_close(
    service: DataService, sources: Sources, clock: Clock, monkeypatch: pytest.MonkeyPatch, caplog
):
    monkeypatch.setattr(binance, "SPARK_FAILURES_IN_A_ROW", 1)  # SOLUSDT stops the round
    sources.down["SOLUSDT"] = 200  # a body that is no list

    await service.refresh_daily_candles()
    asked = [call.request.url.params["symbol"] for call in sources.klines.calls]
    # BTCUSDT and ETHUSDT, then SOLUSDT fails and the rest wait; the second round fails at once.
    assert asked == ["BTCUSDT", "ETHUSDT", "SOLUSDT", "SOLUSDT"]
    eth = sparks(await service.search(None, Market.CRYPTO))["crypto:ETHUSDT"]

    clock.now += RETRY_SECONDS - 1
    await service.refresh_daily_candles()
    assert sources.klines.call_count == 4

    clock.now += 1  # only the unanswered pairs, SOLUSDT still failing
    await service.refresh_daily_candles()
    assert sources.klines.call_count == 6

    clock.now += RETRY_SECONDS
    del sources.down["SOLUSDT"]
    with caplog.at_level(logging.INFO):
        await service.refresh_daily_candles()
    asked = [call.request.url.params["symbol"] for call in sources.klines.calls[6:]]
    assert sorted(asked) == ["ETHBTC", "SOLUSDT", "币安人生USDT"]
    found = sparks(await service.search(None, Market.CRYPTO))
    assert found["crypto:SOLUSDT"] is not None
    assert found["crypto:币安人生USDT"] is not None
    assert found["crypto:ETHUSDT"] == eth  # kept as it was

    clock.now += RETRY_SECONDS  # all answered (ETHBTC is refused): nothing more to ask
    await service.refresh_daily_candles()
    assert sources.klines.call_count == 9


async def test_unanswered_pairs_wait_for_the_next_daily_close_once_it_passed(
    service: DataService, sources: Sources, clock: Clock
):
    sources.down["SOLUSDT"] = 200
    await service.refresh_daily_candles()
    sources.down.clear()

    clock.now = NOW // DAY * DAY + DAY + SETTLE_SECONDS  # the next slot: every pair again
    calls = sources.klines.call_count
    await service.refresh_daily_candles()
    assert sources.klines.call_count - calls == 5


async def test_the_index_follows_the_frame_the_store_adopts(
    service: DataService, sources: Sources, clock: Clock
):
    await service.refresh_daily_candles()
    first = sparks(await service.search(None, Market.CRYPTO))["crypto:BTCUSDT"]

    clock.now += DAY
    await service.refresh_daily_candles()
    second = sparks(await service.search(None, Market.CRYPTO))["crypto:BTCUSDT"]

    assert first[0][0] == CRYPTO_DAYS[0]
    assert [candle[0] for candle in second] == [*CRYPTO_DAYS[1:], CRYPTO_DAYS[-1] + DAY]


async def test_alpaca_daily_bars_have_their_own_share_and_skip_malformed_bars(
    settings: Settings,
    redis: Redis,
    http: httpx.AsyncClient,
    sources: Sources,
    monkeypatch: pytest.MonkeyPatch,
    caplog,
):
    monkeypatch.setattr(alpaca, "SNAPSHOT_SYMBOLS", 1)  # a request per stock
    monkeypatch.setattr(alpaca, "SPARK_SHARE_MAX", 1)  # one a minute
    answer = sources._bars

    def with_a_bad_bar(request: httpx.Request) -> httpx.Response:
        body = answer(request).json()
        body["bars"].setdefault("AAPL", []).append({"t": "2024-11-15T05:00:00Z", "o": "x"})
        return httpx.Response(200, json=body)

    sources.bars.side_effect = with_a_bad_bar
    service = build_data_service(settings, redis, http)
    waited = []

    async def sleep(seconds: float) -> None:
        waited.append(seconds)
        assert not await redis.keys("data:rl:alpaca-stats:*")  # the stats' share is untouched
        await redis.delete(*await redis.keys("data:rl:alpaca-spark:*"))  # the next minute

    monkeypatch.setattr(base, "_sleep", sleep)
    with caplog.at_level(logging.WARNING):
        await service.refresh_daily_candles()

    assert sources.bars.call_count == 3
    assert len(waited) == 2
    assert caplog.text.count("Skipped 3 malformed Alpaca daily bars") == 1
    assert sparks(await service.search(None, Market.STOCK))["stock:AAPL"] is not None

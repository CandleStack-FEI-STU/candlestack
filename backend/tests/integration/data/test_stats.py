"""The 24 h stats: fetched from both sources (mocked with respx), kept in a real Redis, and the
instrument list sorted by them."""

import asyncio
import json
import logging
import time
from datetime import UTC, datetime

import httpx
import polars as pl
import pytest
from redis.asyncio import Redis

from candlestack.core import RateLimiter, Settings
from candlestack.data import (
    DataService,
    InstrumentSort,
    InstrumentStats,
    Market,
    SearchResult,
    build_data_service,
    stats_store,
)
from candlestack.data.cache import Cache, encode_chunk
from candlestack.data.models import STATS_SCHEMA, SourceStats
from candlestack.data.sources import alpaca
from candlestack.data.stats_store import StatsStore

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

# The sample snapshots are of 2026-10-13: their daily bars are fresh the day after.
SNAPSHOTS_AT = datetime(2026, 10, 14, tzinfo=UTC).timestamp()


@pytest.fixture(autouse=True)
def snapshot_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(alpaca, "_time", lambda: SNAPSHOTS_AT)


def ids(found: SearchResult) -> list[str]:
    return [str(instrument.id) for instrument in found.items]


def later(monkeypatch: pytest.MonkeyPatch, seconds: float) -> None:
    """Moves the stats' wall clock ``seconds`` ahead."""
    monkeypatch.setattr(stats_store, "_time", lambda: time.time() + seconds)


def fresh_store(service: DataService) -> StatsStore:
    """A store like the service's, without its process copy: another process."""
    return StatsStore(service._cache, [Market.CRYPTO, Market.STOCK])


async def test_refresh_sorts_the_list_by_volume_in_usd(service: DataService, upstream, caplog):
    upstream.exchange_info()
    upstream.assets()
    ticker = upstream.ticker()
    snapshots = upstream.snapshots()

    with caplog.at_level(logging.INFO):
        await service.refresh_stats()
    found = await service.search(None, limit=100)

    assert ids(found) == [
        "stock:SPY",  # IEX volume only, still more than BTCUSDT in USD
        "crypto:BTCUSDT",
        "crypto:ETHUSDT",
        "stock:AAPL",
        "crypto:SOLUSDT",
        "crypto:ETHBTC",
        "crypto:币安人生USDT",
        "stock:BRK.B",  # its last daily bar is old: no volume
    ]
    stats = dict(zip(ids(found), found.stats, strict=True))
    aapl = stats["stock:AAPL"]
    assert aapl is not None
    assert aapl.price == 247.85
    assert aapl.change_24h == pytest.approx(0.458, abs=1e-3)
    assert aapl.volume_24h == pytest.approx(1375210 * 247.42)
    assert stats["stock:BRK.B"] == InstrumentStats(488.1, None, 0.0)
    assert (ticker.call_count, snapshots.call_count) == (1, 1)
    assert "X-RateLimit-Limit 200, X-RateLimit-Remaining 187; our count this minute" in (
        caplog.text
    )


async def test_gainers_losers_and_symbol_order(service: DataService, upstream):
    upstream.exchange_info()
    upstream.assets()
    upstream.ticker()
    upstream.snapshots()
    await service.refresh_stats()

    gainers = await service.search(None, Market.CRYPTO, sort=InstrumentSort.CHANGE)
    losers = await service.search(None, Market.CRYPTO, sort=InstrumentSort.LOSERS)
    by_symbol = await service.search(None, sort=InstrumentSort.SYMBOL, limit=100)

    assert ids(gainers) == [
        "crypto:ETHUSDT",
        "crypto:BTCUSDT",
        "crypto:币安人生USDT",
        "crypto:SOLUSDT",
        "crypto:ETHBTC",
    ]
    assert ids(losers) == ids(gainers)[::-1]
    assert ids(by_symbol) == sorted(ids(by_symbol), key=lambda found: found.split(":")[1])
    # The ranking of a query stays first: the stock BTC would come first by volume.
    assert ids(await service.search("eth", Market.CRYPTO)) == ["crypto:ETHUSDT", "crypto:ETHBTC"]


async def test_stats_are_not_fetched_again_before_they_are_due(
    service: DataService, upstream, monkeypatch: pytest.MonkeyPatch
):
    upstream.exchange_info()
    upstream.assets()
    ticker = upstream.ticker()
    snapshots = upstream.snapshots()

    await service.refresh_stats()
    await service.refresh_stats()
    assert (ticker.call_count, snapshots.call_count) == (1, 1)

    later(monkeypatch, 301)  # crypto is due after 5 minutes, stocks after 10
    await service.refresh_stats()
    assert (ticker.call_count, snapshots.call_count) == (2, 1)


async def test_another_process_adopts_the_stats_from_redis(service: DataService, upstream):
    upstream.exchange_info()
    upstream.assets()
    ticker = upstream.ticker()
    upstream.snapshots()
    await service.refresh_stats()

    other = fresh_store(service)
    await other.refresh(Market.CRYPTO, fetch=_never)  # stored ones are fresh: not fetched

    table = await other.table()
    assert table.filter(market="crypto").height == 5
    assert ticker.call_count == 1


async def _never():
    raise AssertionError("fetched although the stored stats are fresh")


async def test_a_refresh_in_another_process_is_not_repeated(service: DataService, redis: Redis):
    await redis.set("data:lock:v1:stats:crypto", "someone-else")
    calls = []

    async def fetch():
        calls.append(1)
        raise AssertionError("fetched while another process holds the lock")

    await fresh_store(service).refresh(Market.CRYPTO, fetch)
    assert calls == []


async def test_a_failing_source_keeps_the_last_stats(
    service: DataService, upstream, monkeypatch: pytest.MonkeyPatch, caplog
):
    upstream.exchange_info()
    upstream.assets()
    ticker = upstream.ticker()
    snapshots = upstream.snapshots()
    await service.refresh_stats()
    first = ids(await service.search(None, limit=100))

    ticker.mock(return_value=httpx.Response(503))
    snapshots.mock(side_effect=None, return_value=httpx.Response(401))
    later(monkeypatch, 3600)
    with caplog.at_level(logging.WARNING):
        await service.refresh_stats()

    assert ids(await service.search(None, limit=100)) == first
    assert "Refreshing the crypto stats failed: Binance failed with HTTP 503" in caplog.text
    assert "Refreshing the stock stats failed: Alpaca rejected the API keys" in caplog.text


async def test_old_stats_are_dropped_and_the_list_still_works(
    service: DataService, upstream, redis: Redis, monkeypatch: pytest.MonkeyPatch
):
    upstream.exchange_info()
    upstream.assets()
    upstream.ticker()
    upstream.snapshots()
    await service.refresh_stats()
    await redis.flushdb()  # Redis evicted them; the process still has its copy

    assert ids(await service.search(None, limit=1)) == ["stock:SPY"]

    later(monkeypatch, stats_store.KEEP_SECONDS)
    found = await service.search(None, limit=100)
    assert found.stats == [None] * len(found.items)
    assert ids(found) == sorted(ids(found), key=lambda found: found.split(":")[1])


async def test_unreadable_stored_stats_are_dropped(service: DataService, redis: Redis, caplog):
    await redis.set("data:v1:stats:crypto", b"not arrow")
    await redis.set(
        "data:v1:stats:stock",
        encode_chunk(pl.DataFrame(schema=STATS_SCHEMA).drop("price"), int(time.time())),
    )
    store = fresh_store(service)

    with caplog.at_level(logging.WARNING):
        table = await store.table()

    assert table.height == 0
    assert await redis.exists("data:v1:stats:crypto", "data:v1:stats:stock") == 0
    assert caplog.text.count("Dropping the stored") == 2


async def test_older_stored_stats_are_not_adopted(service: DataService, redis: Redis):
    store = fresh_store(service)
    frame = pl.DataFrame([("BTCUSDT", 1.0, 1.0, 1.0)], schema=STATS_SCHEMA, orient="row")
    now = int(time.time())

    async def fetch():
        return SourceStats(frame)

    await store.refresh(Market.CRYPTO, fetch)
    await redis.set("data:v1:stats:crypto", encode_chunk(frame.clear(), now - 60))
    store._reload_at.clear()

    assert (await store.table()).height == 1


async def test_stats_without_redis_work_in_memory(
    settings: Settings, http: httpx.AsyncClient, upstream
):
    dead = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2)
    service = build_data_service(settings, dead, http)
    upstream.exchange_info()
    upstream.assets()
    upstream.ticker()
    upstream.snapshots()

    await service.refresh_stats()

    assert ids(await service.search(None, limit=1)) == ["stock:SPY"]
    await dead.aclose()


async def test_snapshots_are_paced_to_their_share_of_the_budget(
    settings: Settings, redis: Redis, http: httpx.AsyncClient, upstream, sleeps, monkeypatch
):
    monkeypatch.setattr(alpaca, "SNAPSHOT_SYMBOLS", 1)  # a request per stock
    monkeypatch.setattr(alpaca, "STATS_SHARE_MAX", 2)  # two a minute
    upstream.exchange_info()
    upstream.assets()
    upstream.ticker()
    snapshots = upstream.snapshots()
    service = build_data_service(settings, redis, http)
    waited = []

    async def sleep(seconds: float) -> None:
        waited.append(seconds)
        await redis.flushdb()  # the next minute: the share counter is gone

    monkeypatch.setattr("candlestack.data.sources.base._sleep", sleep)
    await service.refresh_stats()

    assert snapshots.call_count == 3
    assert len(waited) == 1
    assert 0 < waited[0] <= 60
    symbols = [call.request.url.params["symbols"] for call in snapshots.calls]
    assert symbols == ["AAPL", "SPY", "BRK.B"]


async def test_an_unexpected_failure_of_one_market_does_not_stop_the_other(
    service: DataService, upstream, monkeypatch: pytest.MonkeyPatch, caplog
):
    upstream.exchange_info()
    upstream.assets()
    snapshots = upstream.snapshots()

    async def broken(_instruments):
        raise RuntimeError("boom")

    monkeypatch.setattr(service._sources[Market.CRYPTO], "stats", broken)
    with caplog.at_level(logging.ERROR):
        await service.refresh_stats()

    assert "Refreshing the crypto stats failed" in caplog.text
    assert "RuntimeError: boom" in caplog.text
    assert snapshots.call_count == 1
    assert ids(await service.search(None, limit=1)) == ["stock:SPY"]


async def test_an_empty_store_has_the_columns_to_sort_by(redis: Redis):
    table = await StatsStore(Cache(redis), [Market.CRYPTO]).table()

    assert table.columns == ["market", *STATS_SCHEMA]
    assert table.height == 0


async def test_the_refresh_lock_outlasts_a_slow_refresh(
    service: DataService, redis: Redis, monkeypatch: pytest.MonkeyPatch
):
    held = []

    async def fetch():
        # Longer than the lock lasts: it is renewed meanwhile.
        for _ in range(4):
            await asyncio.sleep(0.15)
            held.append(await redis.pttl("data:lock:v1:stats:stock"))
        return SourceStats(pl.DataFrame(schema=STATS_SCHEMA))

    monkeypatch.setattr(stats_store, "LOCK_MS", 200)
    monkeypatch.setattr(stats_store, "RENEW_SECONDS", 0.05)
    await fresh_store(service).refresh(Market.STOCK, fetch)

    assert all(0 < ttl <= 200 for ttl in held)
    assert await redis.exists("data:lock:v1:stats:stock") == 0


async def test_a_lock_taken_over_is_neither_renewed_nor_released(
    service: DataService, redis: Redis, monkeypatch: pytest.MonkeyPatch, caplog
):
    async def fetch():
        # The lock expired and another process took it.
        await redis.set("data:lock:v1:stats:stock", "another-process")
        await asyncio.sleep(0.15)
        return SourceStats(pl.DataFrame(schema=STATS_SCHEMA))

    monkeypatch.setattr(stats_store, "RENEW_SECONDS", 0.05)
    with caplog.at_level(logging.WARNING):
        await fresh_store(service).refresh(Market.STOCK, fetch)

    assert await redis.get("data:lock:v1:stats:stock") == b"another-process"
    assert caplog.text.count("was lost while it ran") == 1


async def test_no_stocks_need_no_snapshots(settings: Settings, redis: Redis, http, upstream):
    snapshots = upstream.snapshots()
    source = alpaca.AlpacaSource(settings, http, RateLimiter(redis), Cache(redis))

    found = await source.stats([])

    assert (found.frame.schema, found.frame.height, found.failed) == (STATS_SCHEMA, 0, frozenset())
    assert snapshots.call_count == 0


def stocks_service(settings: Settings, redis: Redis, http) -> DataService:
    return build_data_service(settings, redis, http)


async def test_a_failed_snapshot_batch_keeps_the_others_and_the_last_stats(
    service: DataService, upstream, redis: Redis, monkeypatch: pytest.MonkeyPatch, caplog
):
    monkeypatch.setattr(alpaca, "SNAPSHOT_SYMBOLS", 1)  # AAPL, SPY, BRK.B: a request each
    upstream.exchange_info()
    upstream.assets()
    upstream.ticker()
    snapshots = upstream.snapshots()
    await service.refresh_stats()
    first = {item.symbol: stats for item, stats in _stocks(await service.search(None, limit=100))}

    # Ten minutes later SPY's request fails twice (the round tries it once more) and AAPL's
    # answer has a new price.
    sample = json.loads(upstream.fixture_bytes("alpaca/snapshots-sample.json"))
    sample["AAPL"]["latestTrade"]["p"] = 250.0

    def answer(request: httpx.Request) -> httpx.Response:
        symbol = request.url.params["symbols"]
        if symbol == "SPY":
            return httpx.Response(503)
        return httpx.Response(200, json={symbol: sample[symbol]})

    snapshots.mock(side_effect=answer)
    later(monkeypatch, 601)
    with caplog.at_level(logging.WARNING):
        await service.refresh_stats()

    now = {item.symbol: stats for item, stats in _stocks(await service.search(None, limit=100))}
    assert now["AAPL"] is not None
    assert now["AAPL"].price == 250.0
    assert now["SPY"] == first["SPY"]  # its last stats stay
    assert now["BRK.B"] == first["BRK.B"]
    asked = [call.request.url.params["symbols"] for call in snapshots.calls[3:]]
    # SPY's request is repeated on 503 (three tries), then once more after the others.
    assert asked == ["AAPL", "SPY", "SPY", "SPY", "BRK.B", "SPY", "SPY", "SPY"]
    assert "Alpaca snapshots of 1 of 3 stocks failed" in caplog.text
    # Stored that way too: another process sees the same.
    table = await fresh_store(service).table()
    assert set(table.filter(market="stock")["symbol"]) == {"AAPL", "SPY", "BRK.B"}


def _stocks(found: SearchResult):
    return [
        (item, stats)
        for item, stats in zip(found.items, found.stats, strict=True)
        if item.market is Market.STOCK
    ]


async def test_when_every_snapshot_batch_fails_the_last_stats_stay(
    service: DataService, upstream, monkeypatch: pytest.MonkeyPatch, caplog
):
    upstream.exchange_info()
    upstream.assets()
    upstream.ticker()
    snapshots = upstream.snapshots()
    await service.refresh_stats()
    first = await service.search(None, Market.STOCK)

    snapshots.mock(
        side_effect=None, return_value=httpx.Response(429, headers={"Retry-After": "30"})
    )
    later(monkeypatch, 601)
    with caplog.at_level(logging.WARNING):
        await service.refresh_stats()

    assert (await service.search(None, Market.STOCK)).stats == first.stats
    assert "Refreshing the stock stats failed: Alpaca is rate limiting our requests" in caplog.text


async def test_malformed_snapshots_are_logged_once_per_round(
    service: DataService, upstream, caplog
):
    upstream.exchange_info()
    upstream.assets()
    upstream.ticker()
    upstream.router.get(f"{upstream.ALPACA_DATA}/v2/stocks/snapshots").respond(
        200, json={"AAPL": {"latestTrade": []}, "SPY": [], "BRK.B": {"latestTrade": {"p": 1.0}}}
    )

    with caplog.at_level(logging.WARNING):
        await service.refresh_stats()

    assert caplog.text.count("Skipped 2 malformed Alpaca snapshots") == 1
    found = await service.search(None, Market.STOCK)
    with_stats = {item.symbol for item, stats in _stocks(found) if stats is not None}
    assert with_stats == {"BRK.B"}


async def test_a_process_reads_only_the_fetch_time_of_stats_it_has(
    service: DataService, upstream, redis: Redis, monkeypatch: pytest.MonkeyPatch
):
    upstream.exchange_info()
    upstream.assets()
    upstream.ticker()
    upstream.snapshots()
    await service.refresh_stats()
    store = fresh_store(service)
    await store.table()
    commands = []
    monitor = store._cache._redis

    for name in ("get", "getrange"):
        original = getattr(monitor, name)

        async def spy(*args, _name=name, _original=original, **kwargs):
            commands.append(_name)
            return await _original(*args, **kwargs)

        monkeypatch.setattr(monitor, name, spy)
    store._reload_at.clear()
    await store.table()

    assert commands == ["getrange", "getrange"]  # unchanged: no blob read


async def test_redis_keeps_the_stats_as_long_as_the_process(
    service: DataService, redis: Redis, monkeypatch: pytest.MonkeyPatch
):
    # The fetch took 20 minutes: Redis keeps the stats until KEEP_SECONDS after it began.
    began = time.time()
    clock = [began]
    monkeypatch.setattr(stats_store, "_time", lambda: clock[0])

    async def fetch():
        clock[0] = began + 1200
        return SourceStats(
            pl.DataFrame([("BTCUSDT", 1.0, 1.0, 1.0)], schema=STATS_SCHEMA, orient="row")
        )

    await fresh_store(service).refresh(Market.CRYPTO, fetch)

    ttl = await redis.ttl("data:v1:stats:crypto")
    assert stats_store.KEEP_SECONDS - 1200 - 2 <= ttl <= stats_store.KEEP_SECONDS - 1200


async def test_stats_too_old_to_keep_are_not_read(
    service: DataService, redis: Redis, monkeypatch: pytest.MonkeyPatch
):
    old = int(time.time()) - stats_store.KEEP_SECONDS
    await redis.set(
        "data:v1:stats:crypto",
        encode_chunk(
            pl.DataFrame([("BTCUSDT", 1.0, 1.0, 1.0)], schema=STATS_SCHEMA, orient="row"), old
        ),
    )

    assert (await fresh_store(service).table()).height == 0
    assert await redis.exists("data:v1:stats:crypto") == 1  # left to expire, not decoded


async def test_carried_over_stats_expire_with_their_own_fetch_time(
    service: DataService, monkeypatch: pytest.MonkeyPatch
):
    clock = [time.time()]
    monkeypatch.setattr(stats_store, "_time", lambda: clock[0])
    store = fresh_store(service)
    both = pl.DataFrame(
        [("AAPL", 1.0, 1.0, 1.0), ("SPY", 2.0, 2.0, 2.0)], schema=STATS_SCHEMA, orient="row"
    )
    aapl = both.filter(symbol="AAPL")

    async def everything():
        return SourceStats(both)

    async def without_spy():
        return SourceStats(aapl, frozenset({"SPY"}))

    await store.refresh(Market.STOCK, everything)
    # Every later refresh cannot ask for SPY: its row is carried over with its own time.
    for _ in range(11):
        clock[0] += stats_store.REFRESH_SECONDS[Market.STOCK]
        await store.refresh(Market.STOCK, without_spy)
        assert set((await store.table())["symbol"]) == {"AAPL", "SPY"}

    clock[0] += stats_store.REFRESH_SECONDS[Market.STOCK]  # SPY's row is 2 hours old now
    assert set((await store.table())["symbol"]) == {"AAPL"}
    await store.refresh(Market.STOCK, without_spy)
    assert set((await store.table())["symbol"]) == {"AAPL"}
    # Stored with each row's time: another process sees the same.
    assert set((await fresh_store(service).table())["symbol"]) == {"AAPL"}


async def test_stats_another_process_stored_while_waiting_for_the_lock_are_not_fetched_again(
    service: DataService, redis: Redis, monkeypatch: pytest.MonkeyPatch
):
    other = StatsStore(Cache(redis), [Market.CRYPTO])
    store = StatsStore(Cache(redis), [Market.CRYPTO])
    fresh = pl.DataFrame([("BTCUSDT", 1.0, 1.0, 1.0)], schema=STATS_SCHEMA, orient="row")
    lock = store._cache.lock

    async def lock_after_another_refresh(name, ttl_ms):
        # The other process refreshes between this one's check and its lock.
        async def fetch():
            return SourceStats(fresh)

        await other.refresh(Market.CRYPTO, fetch)
        return await lock(name, ttl_ms)

    async def never():
        raise AssertionError("fetched although another process has just stored them")

    monkeypatch.setattr(store._cache, "lock", lock_after_another_refresh)
    await store.refresh(Market.CRYPTO, never)

    assert (await store.table()).height == 1
    assert await redis.exists("data:lock:v1:stats:crypto") == 0


async def test_a_refused_batch_is_split_to_find_the_symbol(
    service: DataService, upstream, monkeypatch: pytest.MonkeyPatch, caplog
):
    upstream.exchange_info()
    upstream.assets()
    upstream.ticker()
    sample = json.loads(upstream.fixture_bytes("alpaca/snapshots-sample.json"))

    def answer(request: httpx.Request) -> httpx.Response:
        symbols = request.url.params["symbols"].split(",")
        if "SPY" in symbols:  # Alpaca refuses any request with SPY
            return httpx.Response(400, json={"message": "invalid symbol"})
        return httpx.Response(200, json={symbol: sample[symbol] for symbol in symbols})

    snapshots = upstream.router.get(f"{upstream.ALPACA_DATA}/v2/stocks/snapshots").mock(
        side_effect=answer
    )
    with caplog.at_level(logging.WARNING):
        await service.refresh_stats()

    asked = [call.request.url.params["symbols"] for call in snapshots.calls]
    # AAPL,SPY,BRK.B twice, then halves: AAPL and SPY,BRK.B; then SPY and BRK.B.
    assert asked == [
        "AAPL,SPY,BRK.B",
        "AAPL,SPY,BRK.B",
        "AAPL",
        "SPY,BRK.B",
        "SPY",
        "BRK.B",
    ]
    found = await service.search(None, Market.STOCK)
    with_stats = {item.symbol for item, stats in _stocks(found) if stats is not None}
    assert with_stats == {"AAPL", "BRK.B"}
    assert caplog.text.count("Alpaca refused the snapshots of SPY: no stats for them") == 1


async def test_the_markets_refresh_at_the_same_time(
    service: DataService, upstream, monkeypatch: pytest.MonkeyPatch
):
    upstream.exchange_info()
    upstream.assets()
    crypto_done = asyncio.Event()
    binance, alpaca_source = service._sources[Market.CRYPTO], service._sources[Market.STOCK]

    async def crypto_stats(_instruments):
        crypto_done.set()
        return SourceStats(pl.DataFrame(schema=STATS_SCHEMA))

    async def stock_stats(_instruments):
        # Waits for crypto, as a paced stock refresh would take minutes: crypto must not wait
        # for it.
        await crypto_done.wait()
        return SourceStats(pl.DataFrame(schema=STATS_SCHEMA))

    monkeypatch.setattr(binance, "stats", crypto_stats)
    monkeypatch.setattr(alpaca_source, "stats", stock_stats)

    await asyncio.wait_for(service.refresh_stats(), 5)
    assert crypto_done.is_set()

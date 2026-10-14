"""The 24 h stats: fetched from both sources (mocked with respx), kept in a real Redis, and the
instrument list sorted by them."""

import asyncio
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
from candlestack.data import service as service_module
from candlestack.data.cache import Cache, encode_chunk
from candlestack.data.models import STATS_SCHEMA
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
        "data:v1:stats:stock", encode_chunk(pl.DataFrame(schema=STATS_SCHEMA).drop("price"), 1)
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
        return frame

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


async def test_keep_stats_fresh_runs_rounds_until_cancelled(
    service: DataService, monkeypatch: pytest.MonkeyPatch, caplog
):
    rounds = []

    async def refresh_stats():
        rounds.append(1)
        if len(rounds) == 1:
            raise RuntimeError("boom")

    async def sleep(seconds: float) -> None:
        assert seconds == service_module.STATS_CHECK_SECONDS
        if len(rounds) == 3:
            raise asyncio.CancelledError

    monkeypatch.setattr(service, "refresh_stats", refresh_stats)
    monkeypatch.setattr(service_module, "_sleep", sleep)

    with caplog.at_level(logging.ERROR), pytest.raises(asyncio.CancelledError):
        await service.keep_stats_fresh()

    assert len(rounds) == 3
    assert caplog.text.count("Refreshing the instrument stats failed") == 1


async def test_an_empty_store_has_the_columns_to_sort_by(redis: Redis):
    table = await StatsStore(Cache(redis), [Market.CRYPTO]).table()

    assert table.columns == ["market", *STATS_SCHEMA]
    assert table.height == 0


async def test_the_refresh_lock_outlasts_a_slow_refresh(service: DataService, redis: Redis):
    held = []

    async def fetch():
        held.append(await redis.pttl("data:lock:v1:stats:stock"))
        return pl.DataFrame(schema=STATS_SCHEMA)

    await fresh_store(service).refresh(Market.STOCK, fetch)

    assert 30_000 < held[0] <= stats_store.LOCK_MS
    assert await redis.exists("data:lock:v1:stats:stock") == 0


async def test_no_stocks_need_no_snapshots(settings: Settings, redis: Redis, http, upstream):
    snapshots = upstream.snapshots()
    source = alpaca.AlpacaSource(settings, http, RateLimiter(redis), Cache(redis))

    frame = await source.stats([])

    assert (frame.schema, frame.height) == (STATS_SCHEMA, 0)
    assert snapshots.call_count == 0

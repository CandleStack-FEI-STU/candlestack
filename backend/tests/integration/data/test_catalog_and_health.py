"""Instrument search over the cached catalogs, their background refresh and source health."""

import asyncio
import json
import logging
import time
from collections.abc import Awaitable
from types import SimpleNamespace

import httpx
import pytest

import candlestack.data.catalog_store as catalog_store
from candlestack.core import Settings
from candlestack.data import (
    DataService,
    Market,
    SearchResult,
    SourceUnavailable,
    build_data_service,
)

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


def ids(found: SearchResult) -> list[str]:
    return [str(instrument.id) for instrument in found.items]


async def and_background[T](call: Awaitable[T]) -> T:
    """The result of ``call``, once the background work it started (catalog loads and
    refreshes) is done too."""
    before = asyncio.all_tasks()
    result = await call
    await asyncio.gather(*(asyncio.all_tasks() - before))
    return result


def stale(monkeypatch: pytest.MonkeyPatch) -> None:
    """Moves the wall clock of the catalogs a day and an hour ahead: every list is stale."""
    monkeypatch.setattr(catalog_store, "_time", lambda: time.time() + 25 * 3600)


def with_new_pair(listed: dict) -> dict:
    """``listed`` (an exchangeInfo body) with one more trading pair, NEWUSDT."""
    new = {**listed["symbols"][0], "symbol": "NEWUSDT", "baseAsset": "NEW"}
    return {**listed, "symbols": [*listed["symbols"], new]}


async def test_search_both_markets(service: DataService, upstream):
    catalog = upstream.exchange_info()
    assets = upstream.assets()

    assert ids(await service.search("btc/usdt")) == ["crypto:BTCUSDT"]
    assert ids(await service.search("apple")) == ["stock:AAPL"]
    assert ids(await service.search("brkb")) == ["stock:BRK.B"]
    assert ids(await service.search("币安")) == ["crypto:币安人生USDT"]
    assert ids(await service.search("eth", Market.CRYPTO)) == ["crypto:ETHUSDT", "crypto:ETHBTC"]
    assert ids(await service.search("eth", Market.STOCK)) == []
    assert await service.search("  ") == SearchResult([], [])
    assert (await service.search("btc")).unavailable == []
    assert (catalog.call_count, assets.call_count) == (1, 1)


async def test_search_leaves_out_a_market_that_cannot_be_loaded(service: DataService, upstream):
    upstream.exchange_info()
    assets = upstream.router.get(f"{upstream.ALPACA_API}/v2/assets").respond(503)

    found = await service.search("btcusdt")
    assert (ids(found), found.unavailable) == (["crypto:BTCUSDT"], [Market.STOCK])
    assert (await service.search("apple")) == SearchResult([], [Market.STOCK])
    with pytest.raises(SourceUnavailable, match="Alpaca failed with HTTP 503"):
        await service.search("apple", Market.STOCK)

    assert assets.call_count == 3  # one load with its retries; the failure is then remembered


async def test_search_does_not_wait_for_a_market_being_loaded(
    service: DataService, upstream, redis, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(catalog_store, "LOAD_RETRY_SECONDS", 0)  # retry at once
    upstream.exchange_info()
    answer = asyncio.Event()
    listed = upstream.fixture_bytes("alpaca/assets.json")
    calls = 0

    async def assets(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls <= 3:  # the first load and its two retries
            return httpx.Response(503)
        await answer.wait()  # then Alpaca hangs, like a source that does not answer
        return httpx.Response(200, content=listed)

    upstream.router.get(f"{upstream.ALPACA_API}/v2/assets").mock(side_effect=assets)

    assert (await service.search("apple")).unavailable == [Market.STOCK]
    await redis.delete("data:fail:catalog:stock")  # the error Redis keeps for 10 s
    # Crypto is loaded: the next search answers while stocks are retried in the background.
    found = await asyncio.wait_for(service.search("apple"), timeout=2)
    assert (ids(found), found.unavailable) == ([], [Market.STOCK])
    answer.set()
    for _ in range(200):
        found = await service.search("apple")
        if not found.unavailable:
            break
        await asyncio.sleep(0.01)

    assert (ids(found), found.unavailable) == (["stock:AAPL"], [])
    assert calls == 4


async def test_unreadable_stored_catalog_is_fetched_again(service: DataService, upstream, redis):
    await redis.set("data:v1:catalog:crypto", b'{"fetched_at": "not a list"}')
    info = upstream.exchange_info()

    found = await service.search("btcusdt", Market.CRYPTO)

    assert ids(found) == ["crypto:BTCUSDT"]
    assert info.call_count == 1
    assert json.loads(await redis.get("data:v1:catalog:crypto"))["items"]


async def test_stale_catalog_is_served_while_it_refreshes(
    service: DataService,
    upstream,
    settings: Settings,
    redis,
    http: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    listed = json.loads(upstream.fixture_bytes("binance/rest/exchangeInfo-trading.json"))
    newer = {
        **listed,
        "symbols": [
            *listed["symbols"],
            {**listed["symbols"][0], "symbol": "NEWUSDT", "baseAsset": "NEW"},
        ],
    }
    info = upstream.router.get(f"{upstream.BINANCE_API}/api/v3/exchangeInfo").mock(
        side_effect=[httpx.Response(200, json=listed), httpx.Response(200, json=newer)]
    )

    assert ids(await service.search("new", Market.CRYPTO)) == []
    monkeypatch.setattr(catalog_store, "_time", lambda: time.time() + 25 * 3600)
    assert ids(await service.search("new", Market.CRYPTO)) == []  # the old list, at once
    for _ in range(200):  # the refresh runs in the background
        if info.call_count == 2 and ids(await service.search("new", Market.CRYPTO)):
            break
        await asyncio.sleep(0.01)

    assert ids(await service.search("new", Market.CRYPTO)) == ["crypto:NEWUSDT"]
    assert info.call_count == 2
    # Another process finds the refreshed list in Redis.
    other_process = build_data_service(settings, redis, http)
    assert ids(await other_process.search("new", Market.CRYPTO)) == ["crypto:NEWUSDT"]
    assert info.call_count == 2


async def test_failed_refresh_keeps_the_stale_catalog_until_the_next_try(
    service: DataService,
    upstream,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    caplog.set_level(logging.WARNING)
    clock = [1000.0]  # the monotonic clock of the catalogs, which spaces the refreshes
    monkeypatch.setattr(catalog_store, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    listed = json.loads(upstream.fixture_bytes("binance/rest/exchangeInfo-trading.json"))
    info = upstream.router.get(f"{upstream.BINANCE_API}/api/v3/exchangeInfo").mock(
        side_effect=[
            httpx.Response(200, json=listed),
            *[httpx.Response(503)] * 3,  # the first refresh, with its retries
            httpx.Response(200, json=with_new_pair(listed)),
        ]
    )

    assert ids(await service.search("new", Market.CRYPTO)) == []
    stale(monkeypatch)
    found = await and_background(service.search("new", Market.CRYPTO))
    assert (ids(found), info.call_count) == ([], 4)  # the old list, and the refresh failed
    warnings = [r for r in caplog.records if r.getMessage().startswith("Refreshing the crypto")]
    assert [(r.levelno, r.getMessage()) for r in warnings] == [
        (
            logging.WARNING,
            "Refreshing the crypto catalog failed: Binance failed with HTTP 503. "
            "Try again in a minute.",
        )
    ]

    clock[0] += catalog_store.RETRY_SECONDS - 1
    found = await and_background(service.search("btcusdt", Market.CRYPTO))
    assert (ids(found), info.call_count) == (["crypto:BTCUSDT"], 4)  # no new try yet

    clock[0] += 1
    await and_background(service.search("new", Market.CRYPTO))
    assert ids(await service.search("new", Market.CRYPTO)) == ["crypto:NEWUSDT"]
    assert info.call_count == 5


async def test_crash_of_a_refresh_is_logged_and_the_stale_catalog_served(
    service: DataService,
    upstream,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    listed = upstream.fixture_bytes("binance/rest/exchangeInfo-trading.json")
    upstream.router.get(f"{upstream.BINANCE_API}/api/v3/exchangeInfo").mock(
        side_effect=[httpx.Response(200, content=listed), RuntimeError("a bug")]
    )

    await service.search("btcusdt", Market.CRYPTO)
    stale(monkeypatch)
    with caplog.at_level(logging.WARNING):
        found = await and_background(service.search("btcusdt", Market.CRYPTO))

    assert ids(found) == ["crypto:BTCUSDT"]
    [crash] = [
        r for r in caplog.records if r.getMessage() == "Refreshing the crypto catalog failed"
    ]
    assert crash.levelno == logging.ERROR
    assert crash.exc_info is not None
    assert "RuntimeError: a bug" in caplog.text


async def test_catalog_another_process_refreshed_is_adopted_without_the_source(
    service: DataService,
    upstream,
    settings: Settings,
    redis,
    http: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    other_process = build_data_service(settings, redis, http)
    listed = json.loads(upstream.fixture_bytes("binance/rest/exchangeInfo-trading.json"))
    info = upstream.router.get(f"{upstream.BINANCE_API}/api/v3/exchangeInfo").mock(
        side_effect=[
            httpx.Response(200, json=listed),
            httpx.Response(200, json=with_new_pair(listed)),
        ]
    )
    assert ids(await service.search("new", Market.CRYPTO)) == []
    assert ids(await other_process.search("new", Market.CRYPTO)) == []  # from Redis

    stale(monkeypatch)
    await and_background(other_process.search("new", Market.CRYPTO))  # it refreshes first
    found = await and_background(service.search("new", Market.CRYPTO))

    assert ids(found) == []  # the old list, at once
    assert ids(await service.search("new", Market.CRYPTO)) == ["crypto:NEWUSDT"]
    assert info.call_count == 2  # the load and the other process's refresh


async def test_refresh_is_left_to_the_process_running_it(
    service: DataService, upstream, redis, monkeypatch: pytest.MonkeyPatch
):
    info = upstream.exchange_info()
    await service.search("btcusdt", Market.CRYPTO)
    await redis.set("data:lock:catalog:crypto", "another-process", px=30_000)

    stale(monkeypatch)
    found = await and_background(service.search("btcusdt", Market.CRYPTO))

    assert ids(found) == ["crypto:BTCUSDT"]
    assert info.call_count == 1


async def test_market_that_fails_to_load_in_the_background_stays_out(
    service: DataService, upstream, caplog: pytest.LogCaptureFixture
):
    upstream.exchange_info()
    assets = upstream.router.get(f"{upstream.ALPACA_API}/v2/assets").respond(503)
    await service.search("btcusdt", Market.CRYPTO)  # crypto is loaded, stocks are not

    with caplog.at_level(logging.WARNING):
        found = await and_background(service.search("apple"))
        again = await and_background(service.search("apple"))

    assert (ids(found), found.unavailable) == ([], [Market.STOCK])
    assert (ids(again), again.unavailable) == ([], [Market.STOCK])
    assert "The stock catalog cannot be loaded: Alpaca failed with HTTP 503" in caplog.text
    assert assets.call_count == 3  # one load with its retries: the failure is remembered


async def test_crash_of_a_background_load_is_logged_and_tried_again(
    service: DataService, upstream, caplog: pytest.LogCaptureFixture
):
    upstream.exchange_info()
    listed = upstream.fixture_bytes("alpaca/assets.json")
    assets = upstream.router.get(f"{upstream.ALPACA_API}/v2/assets").mock(
        side_effect=[RuntimeError("a bug"), httpx.Response(200, content=listed)]
    )
    await service.search("btcusdt", Market.CRYPTO)

    with caplog.at_level(logging.WARNING):
        found = await and_background(service.search("apple"))
    # Not remembered like an error of the source: the next search loads the list again.
    await and_background(service.search("apple"))

    assert (ids(found), found.unavailable) == ([], [Market.STOCK])
    [crash] = [r for r in caplog.records if r.getMessage() == "Loading the stock catalog failed"]
    assert (crash.levelno, crash.exc_info is not None) == (logging.ERROR, True)
    assert ids(await service.search("apple")) == ["stock:AAPL"]
    assert assets.call_count == 2


async def test_sources_health_is_checked_once_a_minute(service: DataService, upstream):
    ping = upstream.router.get(f"{upstream.BINANCE_API}/api/v3/ping").respond(200, json={})
    clock = upstream.router.get(f"{upstream.ALPACA_API}/v2/clock").respond(
        200, content=upstream.fixture_bytes("alpaca/clock.json")
    )

    health = await service.sources_health()
    again = await service.sources_health()

    assert health == again
    assert set(health) == {"binance", "alpaca"}
    assert all(each.ok and each.detail is None for each in health.values())
    assert all(isinstance(each.latency_ms, int) for each in health.values())
    assert (ping.call_count, clock.call_count) == (1, 1)


async def test_sources_health_says_what_failed(service: DataService, upstream):
    upstream.router.get(f"{upstream.BINANCE_API}/api/v3/ping").respond(503)
    upstream.router.get(f"{upstream.ALPACA_API}/v2/clock").respond(
        401, content=upstream.fixture_bytes("alpaca/error-no-auth.html")
    )

    health = await service.sources_health()

    assert (health["binance"].ok, health["binance"].latency_ms) == (False, None)
    assert health["binance"].detail == "Binance failed with HTTP 503. Try again in a minute."
    assert health["alpaca"].ok is False
    assert (
        health["alpaca"].detail == "Alpaca rejected the API keys of this server. Try again later."
    )

"""Instrument search over the cached catalogs, their background refresh and source health."""

import asyncio
import json
import time

import httpx
import pytest

import candlestack.data.catalog_store as catalog_store
from candlestack.core import Settings
from candlestack.data import DataService, Instrument, Market, SourceUnavailable, build_data_service

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


def ids(instruments: list[Instrument]) -> list[str]:
    return [str(instrument.id) for instrument in instruments]


async def test_search_both_markets(service: DataService, upstream):
    catalog = upstream.exchange_info()
    assets = upstream.assets()

    assert ids(await service.search("btc/usdt")) == ["crypto:BTCUSDT"]
    assert ids(await service.search("apple")) == ["stock:AAPL"]
    assert ids(await service.search("brkb")) == ["stock:BRK.B"]
    assert ids(await service.search("币安")) == ["crypto:币安人生USDT"]
    assert ids(await service.search("eth", Market.CRYPTO)) == ["crypto:ETHBTC", "crypto:ETHUSDT"]
    assert ids(await service.search("eth", Market.STOCK)) == []
    assert await service.search("  ") == []
    assert (catalog.call_count, assets.call_count) == (1, 1)


async def test_search_leaves_out_a_market_that_cannot_be_loaded(service: DataService, upstream):
    upstream.exchange_info()
    assets = upstream.router.get(f"{upstream.ALPACA_API}/v2/assets").respond(503)

    assert ids(await service.search("btcusdt")) == ["crypto:BTCUSDT"]
    with pytest.raises(SourceUnavailable, match="Alpaca failed with HTTP 503"):
        await service.search("apple", Market.STOCK)

    assert assets.call_count == 3  # one load with its retries; the failure is then remembered


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
        if info.call_count == 2 and await service.search("new", Market.CRYPTO):
            break
        await asyncio.sleep(0.01)

    assert ids(await service.search("new", Market.CRYPTO)) == ["crypto:NEWUSDT"]
    assert info.call_count == 2
    # Another process finds the refreshed list in Redis.
    other_process = build_data_service(settings, redis, http)
    assert ids(await other_process.search("new", Market.CRYPTO)) == ["crypto:NEWUSDT"]
    assert info.call_count == 2


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

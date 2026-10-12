"""Instrument icons from logo.dev (mocked with respx), kept in a real Redis."""

import logging

import httpx
import pytest
from pydantic import SecretStr
from redis.asyncio import Redis

from candlestack.core import RateLimiter, Settings
from candlestack.data import Instrument, InstrumentId, InstrumentNotFound, build_data_service
from candlestack.data import icons as icons_module
from candlestack.data.cache import Cache
from candlestack.data.icons import FALLBACK, FALLBACK_AFTER_FAILURE, Icon, Icons

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

PNG = b"\x89PNG\r\n\x1a\n" + b"\x01" * 32
AAPL = InstrumentId.parse("stock:AAPL")
BRKB = InstrumentId.parse("stock:BRK.B")


def png() -> httpx.Response:
    return httpx.Response(200, content=PNG, headers={"Content-Type": "image/png"})


async def test_a_stock_logo_is_fetched_once(service, upstream, redis: Redis):
    upstream.assets()
    logo = upstream.logo("ticker/AAPL").mock(return_value=png())

    first = await service.icon(AAPL)
    second = await service.icon(AAPL)

    assert first == second == Icon(PNG, "image/png", 86400)
    assert logo.call_count == 1
    assert dict(logo.calls[0].request.url.params) == {
        "token": "test-logo-key",
        "fallback": "404",
        "format": "png",
        "size": "64",
        "retina": "true",
    }
    assert 29 * 86400 < await redis.ttl("data:v1:icon:ticker/AAPL") <= 30 * 86400


async def test_pairs_of_one_base_asset_share_its_logo(service, upstream):
    upstream.exchange_info()
    logo = upstream.logo("crypto/ETH").mock(return_value=png())

    icons = [await service.icon(InstrumentId.parse(i)) for i in ("crypto:ETHUSDT", "crypto:ETHBTC")]

    assert [icon.content for icon in icons] == [PNG, PNG]
    assert logo.call_count == 1


async def test_no_logo_is_the_fallback_for_days(service, upstream, redis: Redis):
    upstream.assets()
    logo = upstream.logo("ticker/AAPL").respond(404, json={"error": "not found"})

    assert await service.icon(AAPL) == FALLBACK
    assert await service.icon(AAPL) == FALLBACK
    assert logo.call_count == 1
    assert 6 * 86400 < await redis.ttl("data:v1:icon:ticker/AAPL") <= 7 * 86400


@pytest.mark.parametrize(
    "failure",
    [
        httpx.Response(503, text="down"),
        httpx.Response(429, headers={"Retry-After": "1"}),
        httpx.ConnectTimeout("timed out"),
        httpx.Response(200, content=b"<svg/>", headers={"Content-Type": "image/svg+xml"}),
    ],
    ids=["5xx", "429", "timeout", "svg"],
)
async def test_a_failing_source_gives_the_fallback_for_a_minute(
    service, upstream, redis: Redis, failure: httpx.Response | Exception, caplog
):
    upstream.assets()
    logo = upstream.logo("ticker/AAPL").mock(side_effect=[failure, png()])

    with caplog.at_level(logging.WARNING):
        assert await service.icon(AAPL) == FALLBACK_AFTER_FAILURE
        assert await service.icon(AAPL) == FALLBACK_AFTER_FAILURE

    assert logo.call_count == 1  # not repeated: the failure is kept a minute
    assert 0 < await redis.ttl("data:v1:icon:ticker/AAPL") <= 60
    assert "test-logo-key" not in caplog.text


@pytest.mark.parametrize("status", [401, 403])
async def test_a_rejected_key_stops_the_calls_for_a_while(service, upstream, caplog, status: int):
    upstream.assets()
    aapl = upstream.logo("ticker/AAPL").respond(status, json={"error": "invalid token"})
    brkb = upstream.logo("ticker/BRK.B").mock(return_value=png())

    with caplog.at_level(logging.ERROR):
        assert await service.icon(AAPL) == FALLBACK_AFTER_FAILURE
        assert await service.icon(BRKB) == FALLBACK_AFTER_FAILURE

    assert (aapl.call_count, brkb.call_count) == (1, 0)
    assert [record.levelname for record in caplog.records] == ["ERROR"]
    assert f"logo.dev rejected our key (HTTP {status})" in caplog.text


async def test_without_redis_logo_dev_is_not_asked(settings: Settings, http, upstream):
    service = build_data_service(settings, Redis.from_url("redis://127.0.0.1:1/0"), http)
    upstream.assets()
    logo = upstream.logo("ticker/AAPL").mock(return_value=png())

    assert await service.icon(AAPL) == FALLBACK_AFTER_FAILURE
    assert logo.call_count == 0


async def test_icons_give_up_waiting_for_a_slot(
    settings: Settings, redis: Redis, http, upstream, monkeypatch
):
    monkeypatch.setattr(icons_module, "SLOT_WAIT", 0.01)
    icons = Icons(settings, http, RateLimiter(redis), Cache(redis))
    logo = upstream.logo("ticker/AAPL").mock(return_value=png())
    aapl = Instrument(AAPL, "Apple", "alpaca", "iex", "NASDAQ")
    for _ in range(icons_module.CONCURRENCY):
        await icons._calls.acquire()

    assert await icons.icon(aapl) == FALLBACK_AFTER_FAILURE
    assert logo.call_count == 0


async def test_our_budget_spent_gives_the_fallback(settings: Settings, redis, http, upstream):
    one_a_minute = settings.model_copy(update={"logo_dev_rate_limit": 1})
    service = build_data_service(one_a_minute, redis, http)
    upstream.assets()
    aapl = upstream.logo("ticker/AAPL").mock(return_value=png())
    brkb = upstream.logo("ticker/BRK.B").mock(return_value=png())

    assert (await service.icon(AAPL)).content == PNG
    assert await service.icon(BRKB) == FALLBACK_AFTER_FAILURE
    assert (aapl.call_count, brkb.call_count) == (1, 0)


async def test_without_a_key_every_icon_is_the_fallback(settings: Settings, redis, http, upstream):
    keyless = settings.model_copy(update={"logo_dev_key": SecretStr("")})
    service = build_data_service(keyless, redis, http)
    upstream.assets()
    logo = upstream.logo("ticker/AAPL").mock(return_value=png())

    assert await service.icon(AAPL) == FALLBACK
    assert logo.call_count == 0


async def test_an_unknown_instrument_is_not_asked_for(service, upstream):
    upstream.assets()
    logo = upstream.logo("ticker/NOPE").mock(return_value=png())

    with pytest.raises(InstrumentNotFound):
        await service.icon(InstrumentId.parse("stock:NOPE"))
    assert logo.call_count == 0


async def test_without_the_catalog_the_fallback_stands_in(service, upstream):
    upstream.router.get(f"{upstream.ALPACA_API}/v2/assets").respond(500, text="down")
    logo = upstream.logo("ticker/AAPL").mock(return_value=png())

    assert await service.icon(AAPL) == FALLBACK_AFTER_FAILURE
    assert logo.call_count == 0

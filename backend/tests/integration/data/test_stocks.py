"""Stock candles through DataService: sessions, 1m bars, 1Day bars and Alpaca's failures."""

import logging
from datetime import UTC, datetime

import httpx
import polars as pl
import pytest
from redis.asyncio import Redis

import candlestack.core.ratelimit as ratelimit_module
from candlestack.core import RateLimiter, Settings
from candlestack.data import (
    DataIntegrityError,
    DataService,
    InstrumentId,
    InstrumentNotFound,
    Market,
    SourceUnavailable,
    Timeframe,
    build_data_service,
)
from candlestack.main import create_app

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

AAPL = InstrumentId.parse("stock:AAPL")
HOUR = 3600
# 2024-06-03 is a normal day (13:30-20:00 UTC); 2024-11-29 closes early (14:30-18:00 UTC).
JUNE_3 = ("2024-06-03T13:30", "2024-06-03T20:00")
NOVEMBER_29 = ("2024-11-29T14:30", "2024-11-29T18:00")


def utc(text: str) -> int:
    return int(datetime.fromisoformat(text).replace(tzinfo=UTC).timestamp())


def period(times: tuple[str, str]) -> tuple[int, int]:
    return utc(times[0]), utc(times[1])


async def get_api(service: DataService, redis: Redis, path: str) -> httpx.Response:
    """``GET path`` from the API app, answered by ``service``."""
    app = create_app(Settings(app_env="test"))
    app.state.data_service = service
    app.state.rate_limiter = RateLimiter(redis)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as client:
        return await client.get(path)


@pytest.fixture
def stocks(upstream) -> None:
    """The Alpaca catalog, the 2024 calendar and the first bar of AAPL."""
    upstream.assets()
    upstream.calendar()
    upstream.first_bar()


@pytest.mark.usefixtures("stocks")
async def test_normal_day_from_1m_bars(service: DataService, upstream):
    june = upstream.bars(
        "1Min",
        "2024-06-01T00:00:00Z",
        "bars-AAPL-1Min-2024-06-03-p0.json",
        "bars-AAPL-1Min-2024-06-03-p1.json",
    )

    minutes = await service.candles(AAPL, Timeframe.M1, *period(JUNE_3))
    hours = await service.candles(AAPL, Timeframe.H1, *period(JUNE_3))
    halves = await service.candles(AAPL, Timeframe.H4, *period(JUNE_3))

    assert minutes.frame.height == 320
    assert minutes.gaps_total == 70  # IEX has no trade in 70 of the 390 minutes
    assert (minutes.source, minutes.feed) == ("alpaca", "iex")
    assert hours.frame["ts"].to_list() == [utc("2024-06-03T13:30") + i * HOUR for i in range(7)]
    assert hours.gaps_total == 0
    assert hours.frame["open"][0] == 191.16  # the first minute's open
    assert hours.frame["close"][-1] == 192.16  # 15:59's close, the last candle is 30 minutes
    assert halves.frame["ts"].to_list() == [utc("2024-06-03T13:30"), utc("2024-06-03T17:30")]
    morning = minutes.frame.filter(pl.col("ts") < utc("2024-06-03T17:30"))
    assert halves.frame.row(0)[1:] == (
        morning["open"][0],
        morning["high"].max(),
        morning["low"].min(),
        morning["close"][-1],
        pytest.approx(morning["volume"].sum()),
    )
    assert june.call_count == 2  # two pages, then the month comes from the cache
    first, second = (call.request.url.params for call in june.calls)
    assert (first["end"], first["feed"], first["adjustment"], first["limit"]) == (
        "2024-06-30T23:59:59Z",
        "iex",
        "all",
        "10000",
    )
    assert second["page_token"] == "QUFQTHxNfDE3MTc0NDM2MDAwMDAwMDAwMDA="


@pytest.mark.usefixtures("stocks")
async def test_early_close_day(service: DataService, upstream):
    upstream.bars("1Min", "2024-11-01T00:00:00Z", "bars-AAPL-1Min-2024-11-29.json")
    upstream.bars_json(
        "1Day",
        "2024-01-01T00:00:00Z",
        upstream.aapl_bars("bars-AAPL-1Day-2024-06.json", "bars-AAPL-1Day-2024-11-25_12-02.json"),
    )

    hours = await service.candles(AAPL, Timeframe.H1, *period(NOVEMBER_29))
    halves = await service.candles(AAPL, Timeframe.H4, *period(NOVEMBER_29))
    days = await service.candles(AAPL, Timeframe.D1, utc("2024-11-25"), utc("2024-12-03"))

    assert hours.frame["ts"].to_list() == [utc("2024-11-29T14:30") + i * HOUR for i in range(4)]
    assert hours.gaps_total == 0
    assert halves.frame["ts"].to_list() == [utc("2024-11-29T14:30")]  # 09:30-13:00 only
    assert days.frame["ts"].to_list() == [
        utc("2024-11-25T14:30"),
        utc("2024-11-26T14:30"),
        utc("2024-11-27T14:30"),
        utc("2024-11-29T14:30"),  # Thanksgiving has no session
        utc("2024-12-02T14:30"),
    ]
    assert days.gaps_total == 0
    early_close = days.frame.row(3)
    assert early_close[1:] == (233.11, 236.09, 232.28, 235.68, 549571.0)
    # The IEX 1Day bar covers the regular session: same prices as the 1m bars of the session.
    assert halves.frame.row(0)[1:5] == early_close[1:5]


@pytest.mark.usefixtures("stocks")
async def test_unknown_stock_is_not_asked_for_bars(service: DataService, upstream):
    with pytest.raises(InstrumentNotFound):
        await service.candles(
            InstrumentId.parse("stock:NOTAREALSYM"),
            Timeframe.D1,
            utc("2024-06-03"),
            utc("2024-06-04"),
        )

    assert all(call.request.url.host != "data.alpaca.test" for call in upstream.router.calls)


@pytest.mark.usefixtures("stocks")
async def test_stock_without_any_bar_yet(service: DataService, upstream):
    spy = InstrumentId.parse("stock:SPY")
    first = upstream.router.get(
        f"{upstream.ALPACA_DATA}/v2/stocks/bars", params={"symbols": "SPY", "limit": "1"}
    ).respond(200, content=upstream.fixture_bytes("alpaca/error-unknown-symbol-multi.json"))

    info = await service.instrument(spy)
    candles = await service.candles(spy, Timeframe.D1, utc("2024-06-03"), utc("2024-06-05"))

    assert info.available_from is None
    assert candles.frame.height == 0
    assert (candles.gaps, candles.gaps_total) == (
        [(utc("2024-06-03T13:30"), utc("2024-06-04T20:00"))],
        2,
    )
    assert first.call_count == 1  # "no bar yet" is remembered for an hour


@pytest.mark.usefixtures("stocks")
async def test_rate_limited_request_is_retried(service: DataService, upstream, sleeps: list[float]):
    november = upstream.router.get(
        f"{upstream.ALPACA_DATA}/v2/stocks/bars",
        params={"timeframe": "1Min", "start": "2024-11-01T00:00:00Z"},
    ).mock(
        side_effect=[
            httpx.Response(429),
            httpx.Response(
                200, content=upstream.fixture_bytes("alpaca/bars-AAPL-1Min-2024-11-29.json")
            ),
        ]
    )

    hours = await service.candles(AAPL, Timeframe.H1, *period(NOVEMBER_29))

    assert hours.frame.height == 4
    assert november.call_count == 2
    assert sleeps == [0.5]


@pytest.mark.usefixtures("stocks")
async def test_our_request_budget(
    settings: Settings, redis, http: httpx.AsyncClient, upstream, monkeypatch: pytest.MonkeyPatch
):
    service = build_data_service(settings.model_copy(update={"alpaca_rate_limit": 3}), redis, http)
    monkeypatch.setattr(ratelimit_module, "_time", lambda: 1_800_000_001.0)  # 59 s to go
    november = upstream.bars("1Min", "2024-11-01T00:00:00Z", "bars-AAPL-1Min-2024-11-29.json")

    # Assets, calendar and the first bar use the budget of 3; the bars would be the 4th.
    with pytest.raises(SourceUnavailable) as info:
        await service.candles(AAPL, Timeframe.H1, *period(NOVEMBER_29))

    assert info.value.detail == (
        "Our Alpaca request budget (3 per minute) is spent. Try again in 59 seconds."
    )
    assert info.value.retry_after == 59
    assert november.call_count == 0


@pytest.mark.usefixtures("stocks")
@pytest.mark.parametrize(
    ("error", "detail", "calls"),
    [
        (
            httpx.ReadTimeout("The read operation timed out"),
            "Alpaca did not answer in time. Try again in a minute.",
            1,
        ),
        (
            httpx.ConnectError("[Errno 111] Connection refused"),
            "Alpaca could not be reached (ConnectError). Try again in a minute.",
            3,  # with its two retries
        ),
    ],
    ids=["timeout", "connection-error"],
)
async def test_alpaca_not_answering_is_unavailable_and_remembered(
    service: DataService,
    upstream,
    redis: Redis,
    error: httpx.HTTPError,
    detail: str,
    calls: int,
):
    november = upstream.router.get(
        f"{upstream.ALPACA_DATA}/v2/stocks/bars",
        params={"timeframe": "1Min", "start": "2024-11-01T00:00:00Z"},
    ).mock(side_effect=error)
    start, end = period(NOVEMBER_29)
    chunk = "candles:stock:AAPL:1m:2024-11"

    with pytest.raises(SourceUnavailable) as info:
        await service.candles(AAPL, Timeframe.H1, start, end)
    response = await get_api(
        service,
        redis,
        f"/api/v1/data/candles?instrument=stock:AAPL&timeframe=1h&start={start}&end={end}",
    )

    assert (info.value.source, info.value.detail, info.value.retry_after) == (
        "alpaca",
        detail,
        None,
    )
    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert "retry-after" not in response.headers
    assert response.json() == {
        "type": "https://candlestack.tech/problems/source-unavailable",
        "title": "Data source unavailable",
        "status": 503,
        "detail": detail,
        "source": "alpaca",
    }
    assert november.call_count == calls  # the second request got the kept error
    assert 0 < await redis.ttl(f"data:fail:{chunk}") <= 10
    assert await redis.exists(f"data:v2:{chunk}") == 0


@pytest.mark.usefixtures("stocks")
async def test_answer_that_is_not_json_is_invalid_data(
    service: DataService, upstream, redis: Redis, caplog: pytest.LogCaptureFixture
):
    # A 200 with a page instead of JSON, as a proxy in front of Alpaca might send.
    november = upstream.router.get(
        f"{upstream.ALPACA_DATA}/v2/stocks/bars",
        params={"timeframe": "1Min", "start": "2024-11-01T00:00:00Z"},
    ).respond(
        200,
        content=b"<html><body><h1>Service Unavailable</h1></body></html>",
        headers={"Content-Type": "text/html"},
    )
    start, end = period(NOVEMBER_29)

    with pytest.raises(DataIntegrityError) as info:
        await service.candles(AAPL, Timeframe.H1, start, end)
    with caplog.at_level(logging.ERROR):
        response = await get_api(
            service,
            redis,
            f"/api/v1/data/candles?instrument=stock:AAPL&timeframe=1h&start={start}&end={end}",
        )

    assert info.value.source == "alpaca"
    assert info.value.detail.startswith("Alpaca sent a response that is not valid JSON")
    assert response.status_code == 502
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "https://candlestack.tech/problems/source-data-invalid",
        "title": "Invalid data from the source",
        "status": 502,
        "detail": "Alpaca sent data for this request that failed validation, so it was not "
        "used. Try again later, or ask for another period.",
        "source": "alpaca",
    }
    assert "Invalid data from alpaca: Alpaca sent a response that is not valid JSON" in (
        caplog.text
    )
    assert november.call_count == 1  # the second request got the kept error
    assert await redis.exists("data:v2:candles:stock:AAPL:1m:2024-11") == 0


async def test_rejected_keys(service: DataService, upstream):
    upstream.router.get(f"{upstream.ALPACA_API}/v2/assets").respond(
        401,
        content=upstream.fixture_bytes("alpaca/error-no-auth.html"),
        headers={"Content-Type": "text/html"},
    )

    with pytest.raises(SourceUnavailable, match="Alpaca rejected the API keys of this server"):
        await service.search("apple", Market.STOCK)


async def test_without_keys_stocks_are_unavailable(redis, http: httpx.AsyncClient, upstream):
    service = build_data_service(Settings(app_env="test"), redis, http)

    with pytest.raises(SourceUnavailable, match=r"Alpaca keys .* are not configured"):
        await service.instrument(AAPL)

    assert not upstream.router.calls

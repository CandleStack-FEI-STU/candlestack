"""The data API over HTTP with a fake DataService: parameters, response shapes, error mapping
and the client rate limit."""

from dataclasses import dataclass, field, replace
from typing import Any

import orjson
import polars as pl
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from candlestack.core import Settings
from candlestack.data import (
    CANDLE_SCHEMA,
    CandleSet,
    DataError,
    DataIntegrityError,
    Instrument,
    InstrumentId,
    InstrumentInfo,
    InstrumentNotFound,
    InvalidRequest,
    Market,
    PeriodOutOfRange,
    SearchResult,
    SourceHealth,
    SourceUnavailable,
    Timeframe,
    TooManyCandles,
)
from candlestack.data.api import get_data_service, get_rate_limiter
from candlestack.data.schemas import CandlesOut, candles_json

PROBLEM = "application/problem+json"
PROBLEMS = "https://candlestack.tech/problems/"

BTCUSDT = Instrument(
    InstrumentId(Market.CRYPTO, "BTCUSDT"), "BTC/USDT", "binance", "spot", base="BTC", quote="USDT"
)
AAPL = Instrument(
    InstrumentId(Market.STOCK, "AAPL"), "Apple Inc. Common Stock", "alpaca", "iex", "NASDAQ"
)
# 2024-06-03T00:00:00Z and 2024-06-04T00:00:00Z
DAY_START, DAY_END = 1717372800, 1717459200


def candle_set(
    instrument_id: InstrumentId, timeframe: Timeframe, start: int, end: int
) -> CandleSet:
    frame = pl.DataFrame(
        {
            "ts": [start, start + 3600, start + 3 * 3600],
            "open": [67491.0, 67612.5, 67580.1],
            "high": [67700.0, 67650.0, 67640.0],
            "low": [67420.2, 67510.0, 67488.8],
            "close": [67612.4, 67540.3, 67601.9],
            "volume": [512.31, 398.07, 0.0],
        },
        schema=CANDLE_SCHEMA,
    )
    return CandleSet(
        instrument=instrument_id,
        timeframe=timeframe,
        start=start,
        end=end,
        source="binance",
        feed="spot",
        frame=frame,
        gaps=[(start + 2 * 3600, start + 3 * 3600)],
        gaps_total=1,
        fingerprint="sha256:" + "ab" * 32,
    )


@dataclass
class FakeDataService:
    """Answers like the DataService; ``error`` is raised by every call when set."""

    error: DataError | None = None
    result: CandleSet | None = None
    health: dict[str, SourceHealth] = field(
        default_factory=lambda: {
            "binance": SourceHealth(ok=True, latency_ms=84, detail=None),
            "alpaca": SourceHealth(ok=True, latency_ms=131, detail=None),
        }
    )
    calls: list[tuple[str, tuple[Any, ...]]] = field(default_factory=list)

    def _called(self, name: str, *args: Any) -> None:
        self.calls.append((name, args))
        if self.error is not None:
            raise self.error

    unavailable: list[Market] = field(default_factory=list)

    async def search(self, q: str, market: Market | None = None, limit: int = 20) -> SearchResult:
        self._called("search", q, market, limit)
        return SearchResult([BTCUSDT, AAPL][:limit], self.unavailable)

    async def instrument(self, instrument_id: InstrumentId) -> InstrumentInfo:
        self._called("instrument", instrument_id)
        if instrument_id != AAPL.id:
            raise InstrumentNotFound(instrument_id)
        return InstrumentInfo(AAPL, tuple(Timeframe), 1595856600, 1790372340, 50000)

    async def candles(
        self, instrument_id: InstrumentId, timeframe: Timeframe, start: int, end: int
    ) -> CandleSet:
        self._called("candles", instrument_id, timeframe, start, end)
        return self.result or candle_set(instrument_id, timeframe, start, end)

    async def sources_health(self) -> dict[str, SourceHealth]:
        self._called("sources_health")
        return self.health


@dataclass
class FakeLimiter:
    """``RateLimiter.hit`` that answers ``wait`` (0 when the limit is off), recording calls."""

    wait: float = 0.0
    calls: list[tuple[str, int]] = field(default_factory=list)

    async def hit(self, key: str, limit: int, cost: int = 1, window: int = 60) -> float:
        self.calls.append((key, limit))
        return self.wait if limit > 0 else 0.0


@pytest.fixture
def service() -> FakeDataService:
    return FakeDataService()


@pytest.fixture
def limiter() -> FakeLimiter:
    return FakeLimiter()


@pytest.fixture
def app(app: FastAPI, service: FakeDataService, limiter: FakeLimiter) -> FastAPI:
    app.dependency_overrides[get_data_service] = lambda: service
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    return app


def problem(response: Any, status: int, slug: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    assert response.headers["content-type"] == PROBLEM
    body = response.json()
    assert body["type"] == PROBLEMS + slug
    assert body["status"] == status
    return body


# --- search ---------------------------------------------------------------------------------


def test_search(client: TestClient, service: FakeDataService) -> None:
    response = client.get("/api/v1/data/instruments", params={"q": "btc"})

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": "crypto:BTCUSDT",
                "market": "crypto",
                "symbol": "BTCUSDT",
                "name": "BTC/USDT",
                "source": "binance",
                "feed": "spot",
                "exchange": None,
                "base": "BTC",
                "quote": "USDT",
            },
            {
                "id": "stock:AAPL",
                "market": "stock",
                "symbol": "AAPL",
                "name": "Apple Inc. Common Stock",
                "source": "alpaca",
                "feed": "iex",
                "exchange": "NASDAQ",
                "base": None,
                "quote": None,
            },
        ],
        "count": 2,
        "unavailable": [],
    }
    assert service.calls == [("search", ("btc", None, 20))]


def test_search_names_a_market_that_cannot_be_searched(
    client: TestClient, service: FakeDataService
) -> None:
    service.unavailable = [Market.STOCK]

    response = client.get("/api/v1/data/instruments?q=btc")

    assert response.status_code == 200
    assert response.json()["unavailable"] == ["stock"]


def test_search_passes_market_and_limit(client: TestClient, service: FakeDataService) -> None:
    response = client.get("/api/v1/data/instruments?q=apple&market=stock&limit=1")

    assert response.json()["count"] == 1
    assert service.calls == [("search", ("apple", Market.STOCK, 1))]


@pytest.mark.parametrize(
    ("query", "detail"),
    [
        ("", "query parameter 'q': Field required"),
        ("q=", "query parameter 'q': String should have at least 1 character"),
        (f"q={'a' * 51}", "query parameter 'q': String should have at most 50 characters"),
        ("q=btc&limit=0", "query parameter 'limit': Input should be greater than or equal to 1"),
        ("q=btc&limit=101", "query parameter 'limit': Input should be less than or equal to 100"),
        ("q=btc&market=forex", "query parameter 'market': Input should be 'crypto' or 'stock'"),
    ],
)
def test_search_validation(
    client: TestClient, service: FakeDataService, query: str, detail: str
) -> None:
    response = client.get(f"/api/v1/data/instruments?{query}")

    assert problem(response, 422, "validation")["detail"] == detail
    assert service.calls == []


def test_search_without_catalog(client: TestClient, service: FakeDataService) -> None:
    service.error = SourceUnavailable("alpaca", "Alpaca did not answer in time. Try again later.")

    response = client.get("/api/v1/data/instruments?q=apple")

    body = problem(response, 503, "source-unavailable")
    assert body["source"] == "alpaca"
    assert "retry-after" not in response.headers


# --- instrument detail ----------------------------------------------------------------------


def test_instrument_detail(client: TestClient, service: FakeDataService) -> None:
    response = client.get("/api/v1/data/instruments/stock:aapl")

    assert response.status_code == 200
    assert response.json() == {
        "id": "stock:AAPL",
        "market": "stock",
        "symbol": "AAPL",
        "name": "Apple Inc. Common Stock",
        "source": "alpaca",
        "feed": "iex",
        "exchange": "NASDAQ",
        "base": None,
        "quote": None,
        "timeframes": ["1m", "5m", "15m", "1h", "4h", "1d"],
        "available_from": 1595856600,
        "available_to": 1790372340,
        "max_candles": 50000,
    }
    assert service.calls == [("instrument", (AAPL.id,))]


def test_instrument_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/data/instruments/crypto:NOPEUSDT")

    body = problem(response, 404, "instrument-not-found")
    assert body["title"] == "Instrument not found"
    assert body["instrument"] == "crypto:NOPEUSDT"
    assert body["detail"] == (
        "Instrument crypto:NOPEUSDT does not exist. Search the instruments to find a valid id."
    )


@pytest.mark.parametrize(
    ("instrument_id", "reason"),
    [
        ("BTCUSDT", "must be <market>:<symbol>"),
        ("forex:EURUSD", "Unknown market 'forex'"),
        ("crypto:BTC-USDT", "Symbol 'BTC-USDT' in instrument id 'crypto:BTC-USDT' is not valid"),
    ],
)
def test_instrument_id_validation(
    client: TestClient, service: FakeDataService, instrument_id: str, reason: str
) -> None:
    response = client.get(f"/api/v1/data/instruments/{instrument_id}")

    body = problem(response, 422, "validation")
    assert body["detail"].startswith("path parameter 'instrument_id': ")
    assert reason in body["detail"]
    assert body["errors"][0]["loc"] == ["path", "instrument_id"]
    assert service.calls == []


def test_instrument_ids_in_other_scripts(client: TestClient, service: FakeDataService) -> None:
    client.get("/api/v1/data/instruments/crypto:%E5%B8%81%E5%AE%89%E4%BA%BA%E7%94%9FUSDT")
    client.get("/api/v1/data/instruments/stock:brk.b")

    assert [call[1][0] for call in service.calls] == [
        InstrumentId(Market.CRYPTO, "币安人生USDT"),
        InstrumentId(Market.STOCK, "BRK.B"),
    ]


# --- candles ----------------------------------------------------------------------------------


def test_candles(client: TestClient, service: FakeDataService) -> None:
    response = client.get(
        "/api/v1/data/candles",
        params={
            "instrument": "crypto:btcusdt",
            "timeframe": "1h",
            "start": DAY_START,
            "end": DAY_END,
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "meta": {
            "instrument": "crypto:BTCUSDT",
            "timeframe": "1h",
            "start": DAY_START,
            "end": DAY_END,
            "source": "binance",
            "feed": "spot",
            "fingerprint": "sha256:" + "ab" * 32,
            "count": 3,
            "gaps": [[DAY_START + 7200, DAY_START + 10800]],
            "gaps_total": 1,
        },
        "t": [DAY_START, DAY_START + 3600, DAY_START + 10800],
        "o": [67491.0, 67612.5, 67580.1],
        "h": [67700.0, 67650.0, 67640.0],
        "l": [67420.2, 67510.0, 67488.8],
        "c": [67612.4, 67540.3, 67601.9],
        "v": [512.31, 398.07, 0.0],
    }
    # The orjson body is exactly what the documented model describes.
    CandlesOut.model_validate_json(response.content, strict=True)
    assert service.calls == [
        ("candles", (BTCUSDT.id, Timeframe.H1, DAY_START, DAY_END)),
    ]


def test_no_candles(client: TestClient, service: FakeDataService) -> None:
    found = candle_set(BTCUSDT.id, Timeframe.H1, DAY_START, DAY_END)
    service.result = replace(found, frame=found.frame.clear(), gaps=[(DAY_START, DAY_END)])

    body = client.get(
        f"/api/v1/data/candles?instrument=crypto:BTCUSDT&timeframe=1h&start={DAY_START}"
        f"&end={DAY_END}"
    ).json()

    assert body["meta"]["count"] == 0
    assert body["meta"]["gaps"] == [[DAY_START, DAY_END]]
    assert body["t"] == body["o"] == body["h"] == body["l"] == body["c"] == body["v"] == []


@pytest.mark.parametrize(
    ("value", "seconds"),
    [
        ("1717372800", DAY_START),
        ("2024-06-03", DAY_START),
        ("2024-06-03T00:00:00Z", DAY_START),
        ("2024-06-03T00:00", DAY_START),
        ("2024-06-03 00:00:00", DAY_START),
        ("2024-06-03T02:00:00+02:00", DAY_START),
        ("2024-06-02T20:00:00-04:00", DAY_START),
        ("2024-06-03T00:00:00.999Z", DAY_START),
        ("2024-06-03T13:30:00Z", DAY_START + 13 * 3600 + 1800),
    ],
)
def test_start_formats(
    client: TestClient, service: FakeDataService, value: str, seconds: int
) -> None:
    response = client.get(
        "/api/v1/data/candles",
        params={"instrument": "stock:AAPL", "timeframe": "1d", "start": value, "end": DAY_END + 1},
    )

    assert response.status_code == 200
    assert service.calls[0][1][2] == seconds


def test_end_formats_and_default(
    client: TestClient, service: FakeDataService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("candlestack.data.api._time", lambda: DAY_END + 0.7)
    base = "/api/v1/data/candles?instrument=stock:AAPL&timeframe=1h&start=2024-06-03"

    client.get(f"{base}&end=2024-06-03T20:00:00Z")
    client.get(base)

    assert [call[1][3] for call in service.calls] == [DAY_START + 20 * 3600, DAY_END]


@pytest.mark.parametrize(
    ("query", "detail"),
    [
        (
            "timeframe=1h&start=2024-06-03",
            "query parameter 'instrument': Field required",
        ),
        (
            "instrument=AAPL&timeframe=1h&start=2024-06-03",
            "query parameter 'instrument': Instrument id 'AAPL' must be <market>:<symbol>, "
            "for example crypto:BTCUSDT or stock:AAPL.",
        ),
        (
            "instrument=stock:AAPL&timeframe=2h&start=2024-06-03",
            "query parameter 'timeframe': Input should be '1m', '5m', '15m', '1h', '4h' or '1d'",
        ),
        (
            "instrument=stock:AAPL&timeframe=1h",
            "query parameter 'start': Field required",
        ),
        (
            "instrument=stock:AAPL&timeframe=1h&start=yesterday",
            "query parameter 'start': 'yesterday' is neither epoch seconds nor an ISO 8601 date "
            "or date-time",
        ),
        (
            "instrument=stock:AAPL&timeframe=1h&start=-1717372800",
            "query parameter 'start': '-1717372800' is neither epoch seconds nor an ISO 8601 "
            "date or date-time",
        ),
        (
            "instrument=stock:AAPL&timeframe=1h&start=2024-06-03T00:00:00+02:00",
            "query parameter 'start': '2024-06-03T00:00:00 02:00' is neither epoch seconds nor an "
            "ISO 8601 date or date-time (in a URL, write + as %2B)",
        ),
        (
            "instrument=stock:AAPL&timeframe=1h&start=1717372800000",
            "query parameter 'start': 1717372800000 is after the year 9999: send epoch seconds, "
            "not milliseconds",
        ),
        (
            "instrument=stock:AAPL&timeframe=1h&start=2024-06-04&end=2024-06-03",
            f"query parameter 'end': end ({DAY_START}) must be after start ({DAY_END})",
        ),
        (
            "instrument=stock:AAPL&timeframe=1h&start=2024-06-03&end=2024-06-03",
            f"query parameter 'end': end ({DAY_START}) must be after start ({DAY_START})",
        ),
    ],
)
def test_candles_validation(
    client: TestClient, service: FakeDataService, query: str, detail: str
) -> None:
    response = client.get(f"/api/v1/data/candles?{query}")

    body = problem(response, 422, "validation")
    assert body["detail"] == detail
    assert service.calls == []


def test_start_in_the_future(
    client: TestClient, service: FakeDataService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("candlestack.data.api._time", lambda: DAY_START)

    response = client.get(
        f"/api/v1/data/candles?instrument=stock:AAPL&timeframe=1h&start={DAY_START}"
    )

    assert problem(response, 422, "validation")["detail"] == (
        f"query parameter 'end': end ({DAY_START}, now) must be after start ({DAY_START})"
    )


def test_all_parameter_errors_at_once(client: TestClient) -> None:
    response = client.get("/api/v1/data/candles?instrument=AAPL&timeframe=2h&start=soon")

    locs = [error["loc"] for error in problem(response, 422, "validation")["errors"]]
    assert locs == [["query", "instrument"], ["query", "timeframe"], ["query", "start"]]


# --- error mapping ----------------------------------------------------------------------------

CANDLES = f"/api/v1/data/candles?instrument=crypto:BTCUSDT&timeframe=1m&start={DAY_START}"


def test_period_out_of_range(client: TestClient, service: FakeDataService) -> None:
    service.error = PeriodOutOfRange(
        "crypto:BTCUSDT", "1m", 1502942400, 1790424000, start=1400000000
    )

    body = problem(client.get(CANDLES), 422, "period-out-of-range")

    assert body == {
        "type": PROBLEMS + "period-out-of-range",
        "title": "Period out of range",
        "status": 422,
        "detail": "crypto:BTCUSDT has 1m candles from 2017-08-17T04:00:00Z (1502942400). "
        "Set start to 1502942400 or later.",
        "instrument": "crypto:BTCUSDT",
        "timeframe": "1m",
        "available_from": 1502942400,
        "available_to": 1790424000,
    }


def test_too_many_candles(client: TestClient, service: FakeDataService) -> None:
    suggestion = (
        "Use 5m or a larger timeframe, or end the period at 2024-02-04T17:20:00Z (1707067200) "
        "or earlier."
    )
    service.error = TooManyCandles(131040, 50000, suggestion)

    body = problem(client.get(CANDLES), 422, "too-many-candles")

    assert body == {
        "type": PROBLEMS + "too-many-candles",
        "title": "Too many candles",
        "status": 422,
        "detail": f"Requested 131040 candles, the maximum is 50000. {suggestion}",
        "requested": 131040,
        "maximum": 50000,
        "suggestion": suggestion,
    }


def test_invalid_request_from_the_service(client: TestClient, service: FakeDataService) -> None:
    service.error = InvalidRequest("stock:AAPL has no 1m candles before 2020-07-27.")

    body = problem(client.get(CANDLES), 422, "validation")

    assert body["title"] == "Invalid request"
    assert body["detail"] == "stock:AAPL has no 1m candles before 2020-07-27."


def test_unknown_instrument_in_candles(client: TestClient, service: FakeDataService) -> None:
    service.error = InstrumentNotFound("crypto:BTCUSDT")

    assert problem(client.get(CANDLES), 404, "instrument-not-found")["instrument"] == (
        "crypto:BTCUSDT"
    )


def test_source_budget_spent(client: TestClient, service: FakeDataService) -> None:
    service.error = SourceUnavailable(
        "alpaca", "Our Alpaca request budget is spent. Try again in 20 s.", retry_after=20
    )

    response = client.get(CANDLES)

    body = problem(response, 503, "source-unavailable")
    assert body["title"] == "Data source unavailable"
    assert body["detail"] == "Our Alpaca request budget is spent. Try again in 20 s."
    assert body["source"] == "alpaca"
    assert response.headers["retry-after"] == "20"


def test_invalid_source_data(
    client: TestClient, service: FakeDataService, caplog: pytest.LogCaptureFixture
) -> None:
    # What failed (here a library message) goes to the log, not to the client.
    service.error = DataIntegrityError(
        'Alpaca bars cannot be read: could not append value: "n/a" of type: str to the '
        "builder; consider increasing `infer_schema_length`",
        source="alpaca",
    )

    body = problem(client.get(CANDLES), 502, "source-data-invalid")

    assert body["source"] == "alpaca"
    assert body["detail"] == (
        "Alpaca sent data for this request that failed validation, so it was not used. "
        "Try again later, or ask for another period."
    )
    assert "infer_schema_length" in caplog.text


def test_invalid_data_of_no_known_source(client: TestClient, service: FakeDataService) -> None:
    service.error = DataIntegrityError("Malformed trading calendar day {'date': 'x'}")

    body = problem(client.get(CANDLES), 502, "source-data-invalid")

    assert body["source"] is None
    assert body["detail"].startswith("The data source sent data for this request that failed")


def test_unknown_data_error_is_a_500(client: TestClient, service: FakeDataService) -> None:
    service.error = DataError("Something new went wrong.")

    problem(client.get(CANDLES), 500, "internal-error")


# --- client rate limit ------------------------------------------------------------------------


def test_rate_limit_key_is_the_cloudflare_client_ip(
    client: TestClient, limiter: FakeLimiter
) -> None:
    client.get(CANDLES, headers={"CF-Connecting-IP": "203.0.113.7"})
    client.get(CANDLES)

    assert limiter.calls == [
        ("data:rl:client:203.0.113.7", 60),
        ("data:rl:client:testclient", 60),
    ]


def test_rate_limited(client: TestClient, service: FakeDataService, limiter: FakeLimiter) -> None:
    limiter.wait = 12.2

    response = client.get(CANDLES)

    body = problem(response, 429, "rate-limited")
    assert response.headers["retry-after"] == "13"
    assert body == {
        "type": PROBLEMS + "rate-limited",
        "title": "Too many requests",
        "status": 429,
        "detail": "More than 60 candle and instrument requests in one minute from this "
        "address. Retry in 13 seconds.",
        "limit": 60,
    }
    assert service.calls == []


def test_rate_limit_comes_before_validation(client: TestClient, limiter: FakeLimiter) -> None:
    limiter.wait = 0.2

    response = client.get("/api/v1/data/candles?instrument=nonsense")

    problem(response, 429, "rate-limited")
    assert response.headers["retry-after"] == "1"


@pytest.mark.parametrize(
    ("address", "key"),
    [
        ("2001:db8:1:2:3:4:5:6", "2001:db8:1:2::/64"),
        ("2001:DB8:1:2::ABCD", "2001:db8:1:2::/64"),
        ("::ffff:203.0.113.7", "203.0.113.7"),
    ],
)
def test_rate_limit_key_of_an_ipv6_client_is_its_64_network(
    client: TestClient, limiter: FakeLimiter, address: str, key: str
) -> None:
    client.get(CANDLES, headers={"CF-Connecting-IP": address})

    assert limiter.calls == [(f"data:rl:client:{key}", 60)]


def test_instrument_detail_is_rate_limited(
    client: TestClient, service: FakeDataService, limiter: FakeLimiter
) -> None:
    # An uncached detail asks the source for the first candle, from the environment's budget.
    client.get("/api/v1/data/instruments/stock:AAPL", headers={"CF-Connecting-IP": "203.0.113.7"})
    limiter.wait = 30

    response = client.get("/api/v1/data/instruments/stock:AAPL")

    problem(response, 429, "rate-limited")
    assert response.headers["retry-after"] == "30"
    assert limiter.calls == [("data:rl:client:203.0.113.7", 60), ("data:rl:client:testclient", 60)]
    assert service.calls == [("instrument", (AAPL.id,))]


def test_search_is_not_rate_limited(client: TestClient, limiter: FakeLimiter) -> None:
    limiter.wait = 30

    assert client.get("/api/v1/data/instruments?q=btc").status_code == 200
    assert limiter.calls == []


class TestRateLimitDisabled:
    @pytest.fixture
    def settings(self) -> Settings:
        return Settings(app_env="test", client_rate_limit=0)

    def test_no_limit(self, client: TestClient, limiter: FakeLimiter) -> None:
        limiter.wait = 30

        assert client.get(CANDLES).status_code == 200
        assert limiter.calls == [("data:rl:client:testclient", 0)]


# --- sources health ---------------------------------------------------------------------------


def test_sources_health(client: TestClient) -> None:
    response = client.get("/api/health/sources")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "sources": {
            "binance": {"status": "ok", "latency_ms": 84, "detail": None},
            "alpaca": {"status": "ok", "latency_ms": 131, "detail": None},
        },
    }


def test_sources_health_with_a_source_down(client: TestClient, service: FakeDataService) -> None:
    service.health["alpaca"] = SourceHealth(ok=False, latency_ms=None, detail="HTTP 401")

    response = client.get("/api/health/sources")

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/json"
    body = response.json()
    assert body["status"] == "error"
    assert body["sources"]["binance"]["status"] == "ok"
    assert body["sources"]["alpaca"] == {
        "status": "error",
        "latency_ms": None,
        "detail": "HTTP 401",
    }


# --- OpenAPI ----------------------------------------------------------------------------------


def test_openapi_documents_the_data_api(client: TestClient) -> None:
    schema = client.get("/api/v1/openapi.json").json()
    paths = schema["paths"]

    candles = paths["/api/v1/data/candles"]["get"]
    assert candles["tags"] == ["data"]
    assert candles["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/CandlesOut"
    }
    assert set(candles["responses"]) == {"200", "404", "422", "429", "502", "503"}
    for status in ("404", "422", "429", "502", "503"):
        assert list(candles["responses"][status]["content"]) == [PROBLEM]
    assert "too-many-candles" in candles["responses"]["422"]["description"]
    detail = paths["/api/v1/data/instruments/{instrument_id}"]["get"]
    assert set(detail["responses"]) == {"200", "404", "422", "429", "502", "503"}
    assert set(paths) >= {
        "/api/v1/data/instruments",
        "/api/v1/data/instruments/{instrument_id}",
        "/api/health/sources",
    }
    assert paths["/api/health/sources"]["get"]["tags"] == ["health"]


def test_candles_json_matches_the_documented_model() -> None:
    body = candle_set(BTCUSDT.id, Timeframe.H1, DAY_START, DAY_END)

    parsed = CandlesOut.model_validate(orjson.loads(candles_json(body)))

    assert parsed.meta.count == 3
    assert parsed.l == [67420.2, 67510.0, 67488.8]

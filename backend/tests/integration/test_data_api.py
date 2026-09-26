"""The client rate limit of the candles endpoint, counted in a real Redis at REDIS_URL."""

import os
import uuid

import polars as pl
import pytest
from fastapi.testclient import TestClient

from candlestack.core import Settings
from candlestack.data import CANDLE_SCHEMA, CandleSet, InstrumentId, Timeframe
from candlestack.data.api import get_data_service
from candlestack.main import create_app

pytestmark = pytest.mark.integration

CANDLES = "/api/v1/data/candles?instrument=crypto:BTCUSDT&timeframe=1h&start=1717372800"
# 30.5 s into a UTC minute: all requests fall into one window, which resets 30 s later.
NOW = 1790000010


class NoCandles:
    async def candles(
        self, instrument_id: InstrumentId, timeframe: Timeframe, start: int, end: int
    ) -> CandleSet:
        return CandleSet(
            instrument_id,
            timeframe,
            start,
            end,
            "binance",
            "spot",
            pl.DataFrame(schema=CANDLE_SCHEMA),
            [],
            0,
            "sha256:" + "0" * 64,
        )


def test_client_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("candlestack.core.ratelimit._time", lambda: NOW + 0.5)
    settings = Settings(
        app_env="test",
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        client_rate_limit=2,
    )
    app = create_app(settings)
    app.dependency_overrides[get_data_service] = lambda: NoCandles()
    # New addresses for every run: the counters of an earlier run are still in Redis.
    one, other = ({"CF-Connecting-IP": f"2001:db8::{uuid.uuid4().hex[:4]}:{n}"} for n in range(2))

    with TestClient(app) as client:
        responses = [client.get(f"{CANDLES}&end={NOW}", headers=one) for _ in range(3)]
        elsewhere = client.get(f"{CANDLES}&end={NOW}", headers=other)

    assert [response.status_code for response in responses] == [200, 200, 429]
    assert responses[2].headers["retry-after"] == "30"
    assert responses[2].json()["limit"] == 2
    assert elsewhere.status_code == 200

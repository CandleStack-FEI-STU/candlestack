"""Fixtures of the experiments integration tests: the app on a real Postgres (emptied before each
test), and signed-in users made straight in the database with their models and backtests.

Test modules cannot import this file, so the helpers they need hang on the ``Account`` the
``ada`` and ``bob`` fixtures return.
"""

import asyncio
import hashlib
import json
import secrets
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from candlestack.core import Settings
from candlestack.main import create_app

ORIGIN = {"Origin": "http://testserver"}
# When the backtests of the tests start: #N an hour after #N-1.
EPOCH = datetime(2026, 10, 1, 12, tzinfo=UTC)
SETUP = {
    "timeframe": "30m",
    "period_start": "2021-01-04",
    "period_end": "2024-12-31",
    "direction": "long",
    "threshold": 0.05,
    "stop_loss_pct": 7,
    "fees_pct": 0.1,
    "slippage_pct": 0.02,
    "benchmark": "bh",
}


async def _run_sql(url: str, statement: str, params: dict[str, Any]) -> list[Any]:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            result = await connection.execute(text(statement), params)
            return list(result.all()) if result.returns_rows else []
    finally:
        await engine.dispose()


@pytest.fixture
def sql(database_url: str) -> Callable[..., list[Any]]:
    """Runs one statement in the test database: ``sql("SELECT id FROM backtests")``, the rows."""
    return lambda statement, **params: asyncio.run(_run_sql(database_url, statement, params))


@pytest.fixture(autouse=True)
def empty_tables(sql: Callable[..., list[Any]]) -> None:
    sql("TRUNCATE users, identities, sessions, user_preferences, models, backtests")


@pytest.fixture
def settings(database_url: str, redis_url: str, tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        database_url=database_url,
        redis_url=redis_url,
        model_storage_dir=tmp_path / "models",
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


class Account:
    """A signed-in user: a row in ``users`` and a session whose cookie each request carries."""

    def __init__(self, client: TestClient, sql: Callable[..., list[Any]], user_id: str) -> None:
        self.id = user_id
        self.email = f"{user_id}@example.com"
        self._client = client
        self._sql = sql
        self._token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        sql(
            "INSERT INTO users VALUES (:id, :name, :email, :now, :now)",
            id=user_id,
            name=user_id,
            email=self.email,
            now=now,
        )
        sql(
            "INSERT INTO sessions VALUES (:hash, :id, :now, :now, :expires)",
            hash=hashlib.sha256(self._token.encode()).digest(),
            id=user_id,
            now=now,
            expires=now + timedelta(days=30),
        )

    def request(self, method: str, url: str, **kwargs: Any) -> httpx2.Response:
        headers = {**ORIGIN, "Cookie": f"session={self._token}", **kwargs.pop("headers", {})}
        self._client.cookies.clear()
        return self._client.request(method, url, headers=headers, **kwargs)

    def backtests(self, **params: Any) -> httpx2.Response:
        return self.request("GET", "/api/v1/backtests", params=params)

    def star(self, backtest_id: str, starred: bool = True) -> httpx2.Response:
        return self.request("PATCH", f"/api/v1/backtests/{backtest_id}", json={"starred": starred})

    def dashboard(self) -> httpx2.Response:
        return self.request("GET", "/api/v1/dashboard")

    def model(self, name: str, framework: str = "keras") -> str:
        """Adds a model straight in the table (its file does not matter here); its ID."""
        model_id = "mdl_" + secrets.token_hex(5)
        self._sql(
            "INSERT INTO models (id, user_id, name, framework, size_bytes, sha256, parameters, "
            "keras_version, created_at) VALUES (:id, :user_id, :name, :framework, 1000, :sha, 1, "
            "'3.15.1', now())",
            id=model_id,
            user_id=self.id,
            name=name,
            framework=framework,
            sha=b"\0" * 32,
        )
        return model_id

    def backtest(
        self,
        number: int,
        *,
        status: str = "finished",
        symbols: tuple[str, ...] = ("AAPL",),
        model_name: str = "lstm.keras",
        model_id: str | None = None,
        sharpe: float | None = 1.0,
        total_return: float | None = 0.1,
        max_drawdown: float | None = -0.1,
        win_rate: float | None = 0.5,
        num_trades: int | None = 100,
        starred: bool = False,
        seeded: bool = False,
    ) -> str:
        """Adds a backtest straight in the table, started `number` hours after ``EPOCH``; its
        ID. A failed one has no results."""
        backtest_id = f"bt_{self.id[4:8]}{number:06d}"
        failed = status == "failed"
        created = EPOCH + timedelta(hours=number)
        self._sql(
            "INSERT INTO backtests (id, user_id, number, status, instruments, representation, "
            "model_id, model_name, model_framework, setup, total_return, buy_and_hold_return, "
            "sharpe, max_drawdown, win_rate, num_trades, duration_s, engine_version, error, "
            "starred, seeded, created_at, finished_at) VALUES (:id, :user_id, :number, :status, "
            "CAST(:instruments AS jsonb), 'renko', :model_id, :model_name, 'keras', "
            "CAST(:setup AS jsonb), :total_return, 0.5, :sharpe, :max_drawdown, :win_rate, "
            ":num_trades, 20, '0.2.0', :error, :starred, :seeded, :created, :finished)",
            id=backtest_id,
            user_id=self.id,
            number=number,
            status=status,
            instruments=json.dumps([{"market": "stock", "symbol": s} for s in symbols]),
            model_id=model_id,
            model_name=model_name,
            setup=json.dumps(SETUP),
            total_return=None if failed else total_return,
            sharpe=None if failed else sharpe,
            max_drawdown=None if failed else max_drawdown,
            win_rate=None if failed else win_rate,
            num_trades=None if failed else num_trades,
            error="It failed." if failed else None,
            starred=starred,
            seeded=seeded,
            created=created,
            finished=created + timedelta(seconds=20),
        )
        return backtest_id


@pytest.fixture
def ada(client: TestClient, sql: Callable[..., list[Any]]) -> Account:
    return Account(client, sql, "usr_adaaaaaaaa")


@pytest.fixture
def bob(client: TestClient, sql: Callable[..., list[Any]]) -> Account:
    return Account(client, sql, "usr_bobbbbbbbb")

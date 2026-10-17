"""Fixtures of the experiments integration tests: the app on a real Postgres, emptied before each
test (tests/integration/conftest.py), and signed-in users with their models and backtests made
straight in the database.

Test modules cannot import this file, so the helpers they need hang on the ``BacktestsUser``
the ``ada`` and ``bob`` fixtures return.
"""

import json
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2
import pytest

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


@pytest.fixture(autouse=True)
def _empty_tables(empty_tables: None) -> None:
    """Every test starts without users."""


class BacktestsUser:
    """A signed-in user (the shared ``Account``: ``id``, ``email``, ``sql``, ``request``), the
    backtests API and rows made straight in the tables."""

    def __init__(self, account: Any) -> None:
        self._account = account

    def __getattr__(self, name: str) -> Any:
        return getattr(self._account, name)

    def backtests(self, **params: Any) -> httpx2.Response:
        return self.request("GET", "/api/v1/backtests", params=params)

    def star(self, backtest_id: str, starred: bool = True) -> httpx2.Response:
        return self.request("PATCH", f"/api/v1/backtests/{backtest_id}", json={"starred": starred})

    def dashboard(self) -> httpx2.Response:
        return self.request("GET", "/api/v1/dashboard")

    def model(self, name: str, framework: str = "keras") -> str:
        """Adds a model straight in the table (its file does not matter here); its ID."""
        model_id = "mdl_" + secrets.token_hex(5)
        self.sql(
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
        equity: dict[str, list[float]] | None = None,
    ) -> str:
        """Adds a backtest straight in the table, started `number` hours after ``EPOCH``; its
        ID. A failed one has no results."""
        backtest_id = f"bt_{self.id[4:8]}{number:06d}"
        failed = status == "failed"
        created = EPOCH + timedelta(hours=number)
        self.sql(
            "INSERT INTO backtests (id, user_id, number, status, instruments, representation, "
            "model_id, model_name, model_framework, setup, total_return, buy_and_hold_return, "
            "sharpe, max_drawdown, win_rate, num_trades, equity, duration_s, engine_version, "
            "error, starred, seeded, created_at, finished_at) VALUES (:id, :user_id, :number, "
            ":status, CAST(:instruments AS jsonb), 'renko', :model_id, :model_name, 'keras', "
            "CAST(:setup AS jsonb), :total_return, 0.5, :sharpe, :max_drawdown, :win_rate, "
            ":num_trades, CAST(:equity AS jsonb), 20, '0.2.0', :error, :starred, :seeded, "
            ":created, :finished)",
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
            equity=None if equity is None else json.dumps(equity),
            error="It failed." if failed else None,
            starred=starred,
            seeded=seeded,
            created=created,
            finished=created + timedelta(seconds=20),
        )
        return backtest_id


@pytest.fixture
def ada(account: Callable[[str], Any]) -> BacktestsUser:
    return BacktestsUser(account("usr_adaaaaaaaa"))


@pytest.fixture
def bob(account: Callable[[str], Any]) -> BacktestsUser:
    return BacktestsUser(account("usr_bobbbbbbbb"))

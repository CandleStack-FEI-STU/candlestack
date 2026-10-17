"""The seed command's data and its refusal of prod, without a database; what it writes is an
integration test (tests/integration/experiments/test_seed.py)."""

import runpy
import sys
from datetime import UTC, datetime, timedelta

import pytest

from candlestack.core import Settings, get_settings
from candlestack.experiments import seed as seed_module
from candlestack.experiments.seed import RUNS, main, seed_backtests, started_at
from candlestack.experiments.store import UserModel

USER_ID = "usr_7f3k2m9qx4"
EVENING = datetime(2026, 10, 17, 18, 30, tzinfo=UTC)


def by_number(backtests):
    return {backtest.number: backtest for backtest in backtests}


def test_the_runs_are_the_mockups_fifteen() -> None:
    assert [run.number for run in RUNS] == list(range(1, 16))
    assert sum(run.starred for run in RUNS) == 5
    assert [run.number for run in RUNS if run.results is None] == [6, 13]


def test_the_backtests_of_the_runs() -> None:
    backtests = by_number(seed_backtests(USER_ID, first_number=1, models=[], now=EVENING))

    newest = backtests[15]
    assert newest.user_id == USER_ID
    assert newest.seeded is True
    assert newest.status == "finished"
    assert newest.representation == "windows"
    assert [item["symbol"] for item in newest.instruments] == [
        "AAPL", "MSFT", "NVDA", "SPY", "TSLA", "AMZN", "META", "GOOGL",
    ]  # fmt: skip
    assert {item["market"] for item in newest.instruments} == {"stock"}
    assert (newest.total_return, newest.buy_and_hold_return) == (0.246, 0.682)
    assert (newest.sharpe, newest.max_drawdown, newest.win_rate) == (0.79, -0.197, 0.512)
    assert (newest.num_trades, newest.duration_s) == (1712, 162.0)
    assert newest.created_at == datetime(2026, 10, 17, 16, 5, tzinfo=UTC)
    assert newest.finished_at == newest.created_at + timedelta(seconds=162)
    assert newest.setup == {
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
    assert backtests[8].setup["direction"] == "both"
    assert backtests[4].setup["threshold"] == 0.1
    assert backtests[14].starred is True
    assert backtests[1].created_at == datetime(2026, 10, 10, 20, 40, tzinfo=UTC)
    assert backtests[10].created_at == datetime(2026, 10, 16, 18, 10, tzinfo=UTC)


def test_a_failed_run_has_its_error_and_no_results() -> None:
    backtests = by_number(seed_backtests(USER_ID, first_number=1, models=[], now=EVENING))

    failed = backtests[13]
    assert failed.status == "failed"
    assert failed.error is not None
    assert failed.error.startswith("blesk-novol-8.keras reads Renko bricks, not a Kagi line.")
    assert failed.representation == "kagi"
    assert [failed.total_return, failed.sharpe, failed.max_drawdown, failed.num_trades] == [
        None
    ] * 4
    assert failed.duration_s == 3.0
    assert backtests[6].error is not None
    assert backtests[6].error.startswith("stockmixer.onnx expects 30 candles per sample.")


def test_the_users_models_are_used_by_name_in_any_case() -> None:
    model = UserModel("mdl_7f3k2m9qx4", "My-TSMixer.keras", "keras")

    backtests = by_number(seed_backtests(USER_ID, first_number=1, models=[model], now=EVENING))

    assert (backtests[9].model_id, backtests[9].model_name) == (model.id, "My-TSMixer.keras")
    assert (backtests[1].model_id, backtests[1].model_name) == (None, "blesk-novol-8.keras")
    assert (backtests[6].model_name, backtests[6].model_framework) == ("stockmixer.onnx", "onnx")
    assert backtests[1].model_framework == "keras"


def test_the_numbers_continue_after_the_users_own() -> None:
    backtests = seed_backtests(USER_ID, first_number=8, models=[], now=EVENING)

    assert [backtest.number for backtest in backtests] == list(range(8, 23))
    assert by_number(backtests)[22].representation == "windows"  # the mockup's #15


def test_early_in_the_day_todays_runs_move_back_but_keep_their_gaps() -> None:
    morning = datetime(2026, 10, 17, 9, 0, tzinfo=UTC)
    today = [run for run in RUNS if run.days_ago == 0]

    starts = [started_at(run, morning) for run in today]

    last = max(starts)
    assert last + timedelta(seconds=162) == morning
    assert sorted(starts) == starts
    assert starts[1] - starts[0] == timedelta(minutes=24)  # 13:58 to 14:22
    yesterday = next(run for run in RUNS if run.days_ago == 1)
    assert started_at(yesterday, morning).date() == morning.date() - timedelta(days=1)


@pytest.fixture
def prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seed_module, "get_settings", lambda: Settings(app_env="prod"))


@pytest.mark.usefixtures("prod")
def test_the_command_refuses_prod(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--email", "ada@example.com"]) == 1
    assert capsys.readouterr().err == (
        "python -m candlestack.experiments.seed: error: APP_ENV is prod: test backtests go to "
        "stage and local accounts only\n"
    )


def test_the_command_needs_an_email(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stopped:
        main([])

    assert stopped.value.code == 2
    assert "--email" in capsys.readouterr().err


def test_python_m_runs_the_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setattr("sys.argv", ["seed", "--email", "ada@example.com"])
    # Run as `python -m` would, not on top of the module this file imported.
    monkeypatch.delitem(sys.modules, "candlestack.experiments.seed")
    get_settings.cache_clear()
    try:
        with pytest.raises(SystemExit) as stopped:
            runpy.run_module("candlestack.experiments.seed", run_name="__main__")
    finally:
        get_settings.cache_clear()

    assert stopped.value.code == 1

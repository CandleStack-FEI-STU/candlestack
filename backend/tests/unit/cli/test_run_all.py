"""``candlestack-bt run-all`` called in-process on a small data folder in ``tmp_path``."""

import hashlib
import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from candlestack.cli import main
from candlestack.cli.run_all import _one_polars_thread
from candlestack.engine import ENGINE_VERSION

HALF_HOUR = 1800
DAY = 86_400
FILES = ["stats.parquet", "trades.parquet", "run.json"]
KEYS = ["stock", "model", "threshold", "stop_loss"]
SETTINGS = ["long_only", "fill", "fee_bps", "slippage_bps"]
LABELS = ["--ts-column", "unix", "--labels", "close", "--timeframe", "30m"]
NO_GAP = {"predictions_without_candle": 0, "candles_without_prediction": 0}


def utc(text: str) -> int:
    return int(datetime.fromisoformat(text).replace(tzinfo=UTC).timestamp())


# Three days of eight 30m candles from 14:30 UTC: enough days for a Sharpe ratio.
OPENS = [utc("2026-01-05 14:30") + day * DAY + k * HALF_HOUR for day in range(3) for k in range(8)]


def candles(shift: float) -> pl.DataFrame:
    """Candles in the supervisor's terms (``unix`` is the close, Int32) that rise and fall;
    each opens at the close before it."""
    closes = [100 + 4 * math.sin(i / 2 + shift) + 0.3 * i for i in range(len(OPENS))]
    starts = [100.0, *closes[:-1]]
    return pl.DataFrame(
        {
            "unix": [ts + HALF_HOUR for ts in OPENS],
            "open": starts,
            "high": [max(pair) + 0.5 for pair in zip(starts, closes, strict=True)],
            "low": [min(pair) - 0.5 for pair in zip(starts, closes, strict=True)],
            "close": closes,
        },
        schema_overrides={"unix": pl.Int32},
    )


def predictions(waves: dict[str, float]) -> pl.DataFrame:
    """One prediction per candle of each model, labelled by the close."""
    return pl.concat(
        pl.DataFrame(
            {
                "unix": [ts + HALF_HOUR for ts in OPENS],
                "model": model,
                "prediction": [0.2 * math.cos(i / wave) for i in range(len(OPENS))],
            },
            schema={"unix": pl.Int64, "model": pl.String, "prediction": pl.Float32},
        )
        for model, wave in waves.items()
    )


def stock(data: Path, name: str, shift: float, waves: dict[str, float]) -> Path:
    folder = data / name
    folder.mkdir(parents=True)
    candles(shift).write_parquet(folder / "candles.parquet")
    predictions(waves).write_parquet(folder / "predictions.parquet")
    return folder


@pytest.fixture
def data(tmp_path: Path) -> Path:
    """Two stocks with the models A and B, and a folder that is no stock."""
    folder = tmp_path / "data"
    stock(folder, "MSFT", 1.0, {"B": 0.7, "A": 1.5})
    stock(folder, "AAPL", 0.0, {"A": 1.5, "B": 0.7})
    (folder / "_raw").mkdir()
    return folder


def run_all(data: Path, out: Path, *options: str) -> int:
    return main(["run-all", "--data", str(data), "--out", str(out), *options])


def run(folder: Path, out: Path, *options: str) -> int:
    return main(
        [
            "run",
            "--candles",
            str(folder / "candles.parquet"),
            "--predictions",
            str(folder / "predictions.parquet"),
            "--out",
            str(out),
            *options,
        ]
    )


def assert_run_gives(
    data: Path, out: Path, keys: tuple[str, str, float, float | None], options: list[str]
) -> None:
    """Runs ``run`` on one combination of ``run-all`` into ``out``."""
    name, model, limit, stop = keys
    stop_option = [] if stop is None else ["--stop-loss", str(stop)]
    assert run(
        data / name, out, *LABELS, "--model", model, "--threshold", str(limit), *stop_option,
        *options,
    ) == 0  # fmt: skip


def combination(keys: tuple[str, str, float, float | None]) -> pl.Expr:
    """Selects the rows of one combination."""
    name, model, limit, stop = keys
    selected = (pl.col("stock") == name) & (pl.col("model") == model)
    selected &= pl.col("threshold") == limit
    return selected & (
        pl.col("stop_loss").is_null() if stop is None else pl.col("stop_loss") == stop
    )


# The combinations and run


def test_each_combination_gives_the_trades_and_stats_of_run(data: Path, tmp_path: Path) -> None:
    signals = ["--long-only"]
    shared = ["--fill", "signal_close", "--fee-bps", "5", "--slippage-bps", "1"]
    out = tmp_path / "all"

    code = run_all(
        data, out, *LABELS, *signals, *shared, "--thresholds", "0,0.05", "--stop-losses",
        "none,0.02",
    )  # fmt: skip

    assert code == 0
    stats_frame = pl.read_parquet(out / "stats.parquet")
    trades = pl.read_parquet(out / "trades.parquet")
    combinations = [
        (name, model, limit, stop)
        for name in ["AAPL", "MSFT"]
        for model in ["A", "B"]
        for limit in [0.0, 0.05]
        for stop in [None, 0.02]
    ]
    assert stats_frame.select(KEYS).rows() == combinations
    assert trades.select(KEYS).unique(maintain_order=True).rows() == [
        keys for keys in combinations if keys in trades.select(KEYS).rows()
    ]
    for index, keys in enumerate(combinations):
        single = tmp_path / f"run{index}"
        assert_run_gives(data, single, keys, [*signals, *shared])
        row = stats_frame.row(index, named=True)
        written = json.loads((single / "stats.json").read_text(encoding="utf-8"))
        assert {name: row[name] for name in written} == written
        assert list(row) == [*KEYS, *SETTINGS, *written]
        assert [row[name] for name in SETTINGS] == [True, "signal_close", 5.0, 1.0]
        assert_frame_equal(
            trades.filter(combination(keys)).drop(KEYS),
            pl.read_parquet(single / "trades.parquet"),
            check_exact=True,
        )
    assert trades.height >= 20


def test_the_defaults_are_runs_defaults(data: Path, tmp_path: Path) -> None:
    out = tmp_path / "all"

    assert run_all(data, out, *LABELS) == 0

    assert run(data / "AAPL", tmp_path / "one", *LABELS, "--model", "B") == 0
    row = pl.read_parquet(out / "stats.parquet").row(1, named=True)
    assert row["stock"] == "AAPL"
    assert row["model"] == "B"
    assert row["threshold"] == 0.0
    assert row["stop_loss"] is None
    assert [row[name] for name in SETTINGS] == [False, "next_open", 0.0, 0.0]
    written = json.loads((tmp_path / "one" / "stats.json").read_text(encoding="utf-8"))
    assert {name: row[name] for name in written} == written


def test_models_picks_the_models_in_its_order(data: Path, tmp_path: Path) -> None:
    out = tmp_path / "all"

    assert run_all(data, out, *LABELS, "--models", "B,A") == 0

    rows = pl.read_parquet(out / "stats.parquet").select("stock", "model").rows()
    assert rows == [("AAPL", "B"), ("AAPL", "A"), ("MSFT", "B"), ("MSFT", "A")]


def test_the_output_does_not_depend_on_jobs(data: Path, tmp_path: Path) -> None:
    options = [*LABELS, "--thresholds", "0,0.1", "--stop-losses", "0.01,none"]
    assert run_all(data, tmp_path / "one", *options) == 0

    assert run_all(data, tmp_path / "two", *options, "--jobs", "2") == 0

    for name in FILES:
        assert (tmp_path / "two" / name).read_bytes() == (tmp_path / "one" / name).read_bytes()


def test_the_workers_get_one_polars_thread_unless_told_otherwise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("POLARS_MAX_THREADS", raising=False)
    with _one_polars_thread():
        assert os.environ["POLARS_MAX_THREADS"] == "1"
    assert "POLARS_MAX_THREADS" not in os.environ

    monkeypatch.setenv("POLARS_MAX_THREADS", "3")
    with _one_polars_thread():
        assert os.environ["POLARS_MAX_THREADS"] == "3"
    assert os.environ["POLARS_MAX_THREADS"] == "3"


# What the run writes and prints


def test_run_json_holds_the_settings_models_hashes_and_align_reports(
    data: Path, tmp_path: Path
) -> None:
    out = tmp_path / "all"
    options = ["--thresholds", "0.1,0", "--stop-losses", "0.05,none", "--fee-bps", "2"]

    assert run_all(data, out, *LABELS, *options) == 0

    def inputs(name: str) -> dict[str, dict[str, str]]:
        return {
            kind: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for kind in ["candles", "predictions"]
            for path in [data / name / f"{kind}.parquet"]
        }

    record = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert record == {
        "engine_version": ENGINE_VERSION,
        "data": str(data),
        "settings": {
            "ts_column": "unix",
            "labels": "close",
            "timeframe_seconds": HALF_HOUR,
            "models": None,
            "thresholds": [0.1, 0.0],
            "long_only": False,
            "fill": "next_open",
            "stop_losses": [0.05, None],
            "fee_bps": 2.0,
            "slippage_bps": 0.0,
        },
        "models": ["A", "B"],
        "stocks": [
            {"stock": name, "inputs": inputs(name), "align": {"A": NO_GAP, "B": NO_GAP}}
            for name in ["AAPL", "MSFT"]
        ],
        "failed": [],
    }
    assert "\r" not in (out / "run.json").read_bytes().decode()


def test_the_summary(data: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "all"

    assert run_all(data, out, *LABELS, "--thresholds", "0,1") == 0

    trades = pl.read_parquet(out / "trades.parquet").height
    captured = capsys.readouterr()
    assert captured.out == (
        f"Wrote stats.parquet, trades.parquet and run.json to {out}\n"
        "  stocks  2 ran, 0 failed\n"
        "  models  2\n"
        "  runs    8\n"
        f"  trades  {trades}\n"
    )
    assert captured.err == ""


# Stocks that fail: reported, and the others still run


def test_a_failing_stock_is_reported_and_the_others_run(
    data: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (data / "EMPTY").mkdir()
    gappy = stock(data, "GAPPY", 0.5, {"A": 1.5})
    predictions({"A": 1.5}).filter(pl.col("unix") != OPENS[3] + HALF_HOUR).write_parquet(
        gappy / "predictions.parquet"
    )
    out = tmp_path / "all"

    code = run_all(data, out, *LABELS)

    assert code == 1
    missing = data / "EMPTY" / "candles.parquet"
    gap = f"Model 'A': 1 candle has no prediction, first at ts {OPENS[3]}"
    err = capsys.readouterr().err.splitlines()
    assert err[0] == f"candlestack-bt run-all: error: EMPTY: No candles file at {missing}"
    assert err[1].startswith(f"candlestack-bt run-all: error: GAPPY: {gap}")
    assert len(err) == 2
    record = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert [entry["stock"] for entry in record["stocks"]] == ["AAPL", "MSFT"]
    assert record["failed"][0] == {"stock": "EMPTY", "error": f"No candles file at {missing}"}
    assert record["failed"][1]["error"].startswith(gap)
    stats_frame = pl.read_parquet(out / "stats.parquet")
    assert stats_frame["stock"].unique(maintain_order=True).to_list() == ["AAPL", "MSFT"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda frame: frame.drop("model"),
            "The predictions file {path} has no column 'model'",
        ),
        (
            lambda frame: frame.with_columns(pl.lit(1).alias("model")),
            "Column 'model' of the predictions file {path} must be text",
        ),
        (
            lambda frame: frame.filter(pl.col("model") == "A"),
            "The predictions file {path} has no model 'B'",
        ),
    ],
)
def test_bad_predictions_fail_their_stock(
    data: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], change, message: str
) -> None:
    path = data / "MSFT" / "predictions.parquet"
    change(pl.read_parquet(path)).write_parquet(path)
    out = tmp_path / "all"

    assert run_all(data, out, *LABELS, "--models", "A,B") == 1

    error = message.format(path=path)
    assert capsys.readouterr().err == f"candlestack-bt run-all: error: MSFT: {error}\n"
    record = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert record["failed"] == [{"stock": "MSFT", "error": error}]
    assert pl.read_parquet(out / "stats.parquet")["stock"].unique().to_list() == ["AAPL"]


def test_when_every_stock_fails_the_files_hold_the_keys_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = tmp_path / "data"
    (data / "AAPL").mkdir(parents=True)
    out = tmp_path / "all"

    assert run_all(data, out) == 1

    assert "AAPL: No candles file" in capsys.readouterr().err
    for name in ["stats.parquet", "trades.parquet"]:
        frame = pl.read_parquet(out / name)
        assert frame.is_empty()
        assert frame.columns == KEYS
    record = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert record["models"] == []
    assert record["stocks"] == []


# Usage errors: exit code 2, no files


def assert_usage_error(
    code: int | str | None, capsys: pytest.CaptureFixture[str], message: str
) -> None:
    assert code == 2
    assert message in capsys.readouterr().err


@pytest.mark.parametrize(
    ("options", "message"),
    [
        (["--thresholds", "0,x"], "argument --thresholds: not a number: 'x'"),
        (["--thresholds", "0.1,0.1"], "argument --thresholds: a value repeats: '0.1,0.1'"),
        (["--thresholds", "-1"], "argument --thresholds: must be 0 or more, got -1"),
        (["--stop-losses", "none,1"], "argument --stop-losses: must be between 0 and 1"),
        (["--stop-losses", "none,none"], "argument --stop-losses: a value repeats"),
        (["--models", "A,,B"], "argument --models: a model name is empty"),
        (["--jobs", "0"], "argument --jobs: must be 1 or more, got 0"),
        (["--jobs", "two"], "argument --jobs: not a whole number: 'two'"),
        (["--fee-bps", "-1"], "argument --fee-bps: must be 0 or more, got -1"),
        (["--labels", "close"], "error: --labels close needs --timeframe"),
    ],
)
def test_bad_options_are_usage_errors(
    data: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    options: list[str],
    message: str,
) -> None:
    out = tmp_path / "out"

    with pytest.raises(SystemExit) as exit_info:
        run_all(data, out, *options)

    assert_usage_error(exit_info.value.code, capsys, message)
    assert not out.exists()


def test_a_missing_data_folder(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        run_all(tmp_path / "nowhere", tmp_path / "out")

    message = f"candlestack-bt run-all: error: --data: no folder at {tmp_path / 'nowhere'}"
    assert_usage_error(exit_info.value.code, capsys, message)


def test_a_data_folder_without_stocks(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / ".cache").mkdir()
    (tmp_path / "notes.txt").write_text("", encoding="utf-8")

    with pytest.raises(SystemExit) as exit_info:
        run_all(tmp_path, tmp_path / "out")

    message = f"candlestack-bt run-all: error: --data: no stock folder in {tmp_path}"
    assert_usage_error(exit_info.value.code, capsys, message)


def test_an_out_that_is_a_file(
    data: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "taken"
    out.write_text("", encoding="utf-8")

    assert run_all(data, out, *LABELS) == 2

    assert capsys.readouterr().err.startswith("candlestack-bt run-all: error: ")
    assert out.read_text(encoding="utf-8") == ""

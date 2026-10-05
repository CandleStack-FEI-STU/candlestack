"""``candlestack-bt run-all``: every stock x model x threshold x stop loss of a data folder.

The data folder holds one folder per stock with ``candles.parquet`` and ``predictions.parquet``
(with a ``model`` column). Each combination runs the steps of ``run`` with the same functions,
so it gives the numbers ``run`` gives with the same options. A stock is read and relabelled
once and aligned once per model; each threshold then makes one signal and each stop loss one
backtest. The run writes three files to ``--out``:

- ``stats.parquet``: one row per combination: the keys, the settings and the statistics;
- ``trades.parquet``: the engine's trades of every combination, after its keys;
- ``run.json``: the settings, the engine version, the models found, each stock's input hashes
  and align reports, and the stocks that failed;

and prints a short summary. A stock whose files the steps refuse, or a model of a stock whose
predictions they refuse, is reported and skipped; the others still run. ``--jobs`` runs stocks
in parallel processes; the output does not depend on it.
"""

import argparse
import contextlib
import dataclasses
import functools
import multiprocessing
import os
import sys
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import polars as pl

from candlestack.cli.run import (
    _PRICES,
    _add_time_labels,
    _fraction,
    _non_negative,
    _sha256,
    _write_json,
    aligned,
    check_time_labels,
    read_input,
)
from candlestack.engine import ENGINE_VERSION, Settings, backtest
from candlestack.metrics import stats
from candlestack.signals import long_only, relabel, threshold

# Read by Polars when it starts, so it reaches the worker processes through their environment.
_THREADS = "POLARS_MAX_THREADS"

# The columns that name a combination, first in both result files.
_KEYS = pl.Schema(
    {"stock": pl.String, "model": pl.String, "threshold": pl.Float64, "stop_loss": pl.Float64}
)


@dataclass(frozen=True, slots=True)
class _Options:
    """What each stock's runs need; sent to the worker processes, so plain values only."""

    ts_column: str
    timeframe_seconds: int | None  # None: the files are labelled by the candle's open
    allow_gaps: bool
    models: tuple[str, ...] | None  # None: every model of each stock
    thresholds: tuple[float, ...]
    stop_losses: tuple[float | None, ...]
    long_only: bool
    fill: Literal["next_open", "signal_close"]
    fee_bps: float
    slippage_bps: float


@dataclass(frozen=True, slots=True)
class _Failed:
    """A stock whose files the steps refused (``model`` None), or one model of it, and why."""

    stock: str
    model: str | None
    error: str


@dataclass(frozen=True, slots=True)
class _Ran:
    """One stock's runs: its rows of both result files (None when none of its models ran),
    its entry in ``run.json`` and its models that failed."""

    stock: str
    stats: pl.DataFrame | None
    trades: pl.DataFrame | None
    record: dict[str, Any]
    failed: tuple[_Failed, ...]


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Adds the options of ``run-all`` to its parser, in groups for its help."""
    files = parser.add_argument_group("files")
    files.add_argument(
        "--data",
        type=Path,
        required=True,
        metavar="DIR",
        help="folder with one folder per stock holding candles.parquet and predictions.parquet "
        "(folders whose name starts with _ or . are no stocks)",
    )
    files.add_argument(
        "--out",
        type=Path,
        required=True,
        metavar="DIR",
        help="folder the three result files go to, created if needed",
    )
    _add_time_labels(parser)
    signals = parser.add_argument_group("signals")
    signals.add_argument(
        "--allow-gaps",
        action="store_true",
        help="as run's --allow-gaps, for every stock and model; run.json counts the gaps",
    )
    signals.add_argument(
        "--models",
        type=_models,
        default=None,
        metavar="NAMES",
        help="comma-separated models to backtest, or all (default: all models of each stock)",
    )
    signals.add_argument(
        "--thresholds",
        type=_list(_non_negative),
        default=(0.0,),
        metavar="LIMITS",
        help="comma-separated thresholds, each as run's --threshold (default: 0)",
    )
    signals.add_argument("--long-only", action="store_true", help="flat instead of short")
    _add_engine(parser)


def _add_engine(parser: argparse.ArgumentParser) -> None:
    engine = parser.add_argument_group("engine")
    engine.add_argument(
        "--fill",
        choices=["next_open", "signal_close"],
        default="next_open",
        help="fill a decision at the next candle's open or at the close of its own candle "
        "(default: next_open)",
    )
    engine.add_argument(
        "--stop-losses",
        type=_list(_stop_loss),
        default=(None,),
        metavar="FRACTIONS",
        help="comma-separated stop losses, each as run's --stop-loss or none for no stop "
        "(default: none)",
    )
    engine.add_argument(
        "--fee-bps",
        type=_non_negative,
        default=0.0,
        metavar="BPS",
        help="the fee of each leg, in basis points of its notional (default: 0)",
    )
    engine.add_argument(
        "--slippage-bps",
        type=_non_negative,
        default=0.0,
        metavar="BPS",
        help="how far each fill lands from its price, against the trade (default: 0)",
    )
    engine.add_argument(
        "--jobs",
        type=_positive_int,
        default=1,
        metavar="N",
        help="run N stocks at a time in their own processes (default: 1, in this process)",
    )


def run_all(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    """Runs every combination with the options in ``args`` and returns the exit code.

    A wrong option stops at ``parser.error`` (exit code 2), and so does a data folder that is
    missing or holds no stock folder; an ``--out`` it cannot write to prints the reason and
    returns 2. A stock or a model of a stock that fails is named on stderr and in ``run.json``
    and the exit code is 1; otherwise it is 0.
    """
    check_time_labels(args, parser)
    if not args.data.is_dir():
        parser.error(f"--data: no folder at {args.data}")
    folders = sorted(
        path
        for path in args.data.iterdir()
        if path.is_dir() and not path.name.startswith(("_", "."))
    )
    if not folders:
        parser.error(f"--data: no stock folder in {args.data}")
    options = _options(args)
    outcomes = _outcomes(options, folders, args.jobs)
    ran = [outcome for outcome in outcomes if isinstance(outcome, _Ran)]
    failed = [
        failure
        for outcome in outcomes
        for failure in (outcome.failed if isinstance(outcome, _Ran) else (outcome,))
    ]
    for failure in failed:
        where = failure.stock if failure.model is None else f"{failure.stock} {failure.model!r}"
        sys.stderr.write(f"{parser.prog}: error: {where}: {failure.error}\n")
    try:
        _write(args, options, ran, failed)
    except OSError as error:
        sys.stderr.write(f"{parser.prog}: error: {error}\n")
        return 2
    sys.stdout.write(_summary(args.out, ran, failed))
    return 1 if failed else 0


def _options(args: argparse.Namespace) -> _Options:
    return _Options(
        ts_column=args.ts_column,
        timeframe_seconds=args.timeframe,
        allow_gaps=args.allow_gaps,
        models=args.models,
        thresholds=args.thresholds,
        stop_losses=args.stop_losses,
        long_only=args.long_only,
        fill=args.fill,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
    )


def _outcomes(options: _Options, folders: list[Path], jobs: int) -> list[_Ran | _Failed]:
    """Each stock's outcome, in the order of ``folders`` whatever ``jobs`` is."""
    work = functools.partial(_stock, options)
    if jobs == 1 or len(folders) == 1:
        return [work(folder) for folder in folders]
    # spawn, not fork: a forked copy of a process that runs Polars' threads can hang.
    context = multiprocessing.get_context("spawn")
    with (
        _one_polars_thread(),
        ProcessPoolExecutor(min(jobs, len(folders)), mp_context=context) as pool,
    ):
        return list(pool.map(work, folders))


@contextlib.contextmanager
def _one_polars_thread() -> Iterator[None]:
    """Starts the worker processes with one Polars thread each, unless POLARS_MAX_THREADS
    says otherwise: the frames of one run are small, and a pool of threads per process costs
    more than it saves once the processes share the cores."""
    if _THREADS in os.environ:
        yield
        return
    os.environ[_THREADS] = "1"
    try:
        yield
    finally:
        del os.environ[_THREADS]


# What ``run`` turns into its exit code 2: a missing file, data a step refuses (the engine's
# InvalidInput is a ValueError) or data no step checks for, which Polars refuses.
_REFUSED = (OSError, ValueError, pl.exceptions.PolarsError)


def _stock(options: _Options, folder: Path) -> _Ran | _Failed:
    """All combinations of the stock in ``folder``, or why its files were refused."""
    try:
        return _runs(options, folder)
    except _REFUSED as error:
        return _Failed(folder.name, None, _reason(error))


def _runs(options: _Options, folder: Path) -> _Ran:
    files = {name: folder / f"{name}.parquet" for name in ["candles", "predictions"]}
    candles, predictions = _read_stock(options, files)
    source = files["predictions"]
    found = _found_models(predictions, source)
    stats_rows: list[pl.DataFrame] = []
    trades: list[pl.DataFrame] = []
    reports: dict[str, Any] = {}
    failed: list[_Failed] = []
    for model in found if options.models is None else options.models:
        try:
            if model not in found:
                raise ValueError(f"The predictions file {source} has no model {model!r}")
            frame, report = aligned(
                candles,
                predictions,
                timeframe=None,
                model=model,
                allow_gaps=options.allow_gaps,
                source=source,
            )
            runs = _model_runs(options, frame)
        except _REFUSED as error:  # the other models of the stock still run
            failed.append(_Failed(folder.name, model, _reason(error)))
            continue
        reports[model] = dataclasses.asdict(report)
        for keys, values, result_trades in runs:
            row = {"stock": folder.name, "model": model, **keys}
            stats_rows.append(pl.DataFrame([{**row, **_settings(options), **values}]))
            trades.append(result_trades.select(*_key_columns(row), pl.all()))
    record = {
        "stock": folder.name,
        "inputs": {
            name: {"path": str(path), "sha256": _sha256(path)} for name, path in files.items()
        },
        "align": reports,
    }
    if not stats_rows:  # every model failed
        return _Ran(folder.name, None, None, record, tuple(failed))
    return _Ran(folder.name, _stats_frame(stats_rows), pl.concat(trades), record, tuple(failed))


def _read_stock(options: _Options, files: dict[str, Path]) -> tuple[pl.DataFrame, pl.DataFrame]:
    """The candles and predictions of a stock, both labelled by the candle's open."""
    candles = read_input(files["candles"], "candles", options.ts_column, _PRICES)
    predictions = read_input(
        files["predictions"], "predictions", options.ts_column, ["prediction", "model"]
    )
    # Relabelled once here, not by ``aligned`` once per model.
    if options.timeframe_seconds is not None:
        candles = relabel(candles, options.timeframe_seconds)
        predictions = relabel(predictions, options.timeframe_seconds)
    return candles, predictions


def _found_models(predictions: pl.DataFrame, path: Path) -> list[str]:
    """The models in the predictions file, by name."""
    if predictions.schema["model"] != pl.String:
        raise ValueError(f"Column 'model' of the predictions file {path} must be text")
    found = sorted(predictions["model"].drop_nulls().unique().to_list())
    if not found:
        raise ValueError(f"The predictions file {path} names no model: column 'model' is empty")
    return found


def _reason(error: Exception) -> str:
    """The message of ``error`` on one line, as ``run`` prints it."""
    return " ".join(str(error).split())


def _model_runs(
    options: _Options, frame: pl.DataFrame
) -> list[tuple[dict[str, Any], dict[str, Any], pl.DataFrame]]:
    """``run``'s steps after ``align`` for each threshold and stop loss: their keys,
    statistics and trades."""
    runs = []
    for limit in options.thresholds:
        signal = threshold(frame["prediction"], limit)
        if options.long_only:
            signal = long_only(signal)
        signed = frame.with_columns(signal)
        for stop_loss in options.stop_losses:
            settings = Settings(
                fill=options.fill,
                stop_loss=stop_loss,
                fee_bps=options.fee_bps,
                slippage_bps=options.slippage_bps,
            )
            result = backtest(signed, settings)
            values = stats(result.trades, result.series, frame)
            runs.append(({"threshold": limit, "stop_loss": stop_loss}, values, result.trades))
    return runs


def _settings(options: _Options) -> dict[str, Any]:
    """The settings every combination shares, as columns of ``stats.parquet``."""
    return {
        "long_only": options.long_only,
        "fill": options.fill,
        "fee_bps": options.fee_bps,
        "slippage_bps": options.slippage_bps,
    }


def _key_columns(row: dict[str, Any]) -> list[pl.Expr]:
    return [pl.lit(row[name], dtype).alias(name) for name, dtype in _KEYS.items()]


def _stats_frame(rows: list[pl.DataFrame]) -> pl.DataFrame:
    """The rows as one frame with the key types; a value that is None in every row is
    Float64, not Null, so the frames of all stocks concatenate."""
    frame = pl.concat(rows, how="vertical_relaxed")
    return frame.with_columns(pl.col(pl.Null).cast(pl.Float64)).cast(_KEYS)


def _write(
    args: argparse.Namespace, options: _Options, ran: list[_Ran], failed: list[_Failed]
) -> None:
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    stats_frames = [outcome.stats for outcome in ran if outcome.stats is not None]
    if stats_frames:
        stats_frame = pl.concat(stats_frames, how="vertical_relaxed")
        trades = pl.concat([outcome.trades for outcome in ran if outcome.trades is not None])
    else:  # nothing ran: the keys alone, as the other columns come from the runs
        stats_frame = trades = pl.DataFrame(schema=_KEYS)
    stats_frame.write_parquet(out / "stats.parquet")
    trades.write_parquet(out / "trades.parquet")
    _write_json(out / "run.json", _record(args, options, ran, failed))


def _record(
    args: argparse.Namespace, options: _Options, ran: list[_Ran], failed: list[_Failed]
) -> dict[str, Any]:
    """What ``run.json`` holds: enough to repeat the run and to tell whether its inputs
    changed."""
    return {
        "engine_version": ENGINE_VERSION,
        "data": str(args.data),
        "settings": {
            "ts_column": args.ts_column,
            "labels": args.labels,
            "timeframe_seconds": args.timeframe,
            "allow_gaps": options.allow_gaps,
            "models": None if options.models is None else list(options.models),
            "thresholds": list(options.thresholds),
            "long_only": options.long_only,
            "fill": options.fill,
            "stop_losses": list(options.stop_losses),
            "fee_bps": options.fee_bps,
            "slippage_bps": options.slippage_bps,
        },
        "models": _models_found(ran),
        "stocks": [outcome.record for outcome in ran],
        "failed": [dataclasses.asdict(failure) for failure in failed],
    }


def _models_found(ran: list[_Ran]) -> list[str]:
    return sorted({model for outcome in ran for model in outcome.record["align"]})


def _summary(out: Path, ran: list[_Ran], failed: list[_Failed]) -> str:
    stocks = sum(failure.model is None for failure in failed)
    rows = [
        ("stocks", f"{len(ran)} ran, {stocks} failed"),
        ("models", f"{len(_models_found(ran))} ran, {len(failed) - stocks} failed on a stock"),
        ("runs", sum(_height(outcome.stats) for outcome in ran)),
        ("trades", sum(_height(outcome.trades) for outcome in ran)),
    ]
    lines = [
        f"Wrote stats.parquet, trades.parquet and run.json to {out}",
        *(f"  {name:<8}{value}" for name, value in rows),
    ]
    return "\n".join(lines) + "\n"


def _height(frame: pl.DataFrame | None) -> int:
    return 0 if frame is None else frame.height


def _list[T](item: Callable[[str], T]) -> Callable[[str], tuple[T, ...]]:
    """An argparse type: comma-separated values, each of the type ``item``, none repeated."""

    def parse(text: str) -> tuple[T, ...]:
        values = tuple(item(part.strip()) for part in text.split(","))
        if len(set(values)) < len(values):
            raise argparse.ArgumentTypeError(f"a value repeats: {text!r}")
        return values

    return parse


def _models(text: str) -> tuple[str, ...] | None:
    """``all`` or comma-separated model names (an argparse type)."""
    return None if text == "all" else _list(_model)(text)


def _model(text: str) -> str:
    if not text:
        raise argparse.ArgumentTypeError("a model name is empty")
    return text


def _stop_loss(text: str) -> float | None:
    """``none`` or a stop loss as for run's ``--stop-loss`` (an argparse type)."""
    return None if text == "none" else _fraction(text)


def _positive_int(text: str) -> int:
    """A whole number of 1 or more (an argparse type)."""
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a whole number: {text!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be 1 or more, got {text}")
    return value

"""``candlestack-bt run``: one backtest of a model's predictions on the candles of one stock.

The steps are the public functions of the backtest modules, so a run from code gives the same
numbers: read both Parquet files, name their time column ``ts``, ``relabel`` both when they are
labelled by the candle's close, ``align`` (strict unless ``--allow-gaps``), the post-processing
of the predictions into the signal (``make_signal``: calibration, ``ema``, one rule, ``long_only``,
``confirm``, ``min_hold``, in that order, each off unless asked for), ``backtest``, ``stats``.
The run writes four files to ``--out``:

- ``trades.parquet``: the engine's trades;
- ``series.parquet``: the engine's series with its ``drawdown``;
- ``stats.json``: the statistics, None as null;
- ``run.json``: the settings, the post-processing, the engine version, the SHA-256 of both
  input files and the align report;

and prints a short summary of the statistics.

``check_time_labels``, ``read_input``, ``aligned`` and the post-processing (``PostProcessing``,
``add_post_processing``, ``check_post_processing``, ``post_processing``, ``rule_limit``,
``prepare``, ``decide``, ``make_signal``, ``describe``) are public in this module so that other
commands read, align and post-process the same way, in the same order.
"""

import argparse
import dataclasses
import hashlib
import json
import math
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import polars as pl

from candlestack.engine import Result, Settings, backtest
from candlestack.metrics import drawdown, stats
from candlestack.signals import (
    AlignReport,
    align,
    confirm,
    ema,
    hysteresis,
    kmeans,
    long_only,
    min_hold,
    rank,
    relabel,
    threshold,
    zscore,
)

Stats = dict[str, float | int | None]
Calibration = Literal["zscore", "rank"]
Rule = Literal["threshold", "hysteresis", "kmeans"]

_PRICES = ["open", "high", "low", "close"]
_TIMEFRAME = re.compile(r"([1-9][0-9]*)([mhd])")
_UNIT_SECONDS = {"m": 60, "h": 3_600, "d": 86_400}


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Adds the options of ``run`` to its parser, in groups for its help."""
    _add_files(parser)
    _add_time_labels(parser)
    _add_signals(parser)
    add_post_processing(parser, grid=False)
    _add_engine(parser)


def _add_files(parser: argparse.ArgumentParser) -> None:
    files = parser.add_argument_group("files")
    files.add_argument(
        "--candles",
        type=Path,
        required=True,
        metavar="PATH",
        help="Parquet file of the candles: the time column, open, high, low and close",
    )
    files.add_argument(
        "--predictions",
        type=Path,
        required=True,
        metavar="PATH",
        help="Parquet file of the predictions: the time column, prediction (and model)",
    )
    files.add_argument(
        "--out",
        type=Path,
        required=True,
        metavar="DIR",
        help="folder the four result files go to, created if needed",
    )


def _add_time_labels(parser: argparse.ArgumentParser) -> None:
    labels = parser.add_argument_group("time labels")
    labels.add_argument(
        "--ts-column",
        default="ts",
        metavar="NAME",
        help="the time column of both files, integer UTC epoch seconds (default: ts; the "
        "supervisor's files: unix)",
    )
    labels.add_argument(
        "--labels",
        choices=["open", "close"],
        default="open",
        help="whether the time is a candle's open or its close (default: open); close "
        "moves the times of both files back by --timeframe",
    )
    labels.add_argument(
        "--timeframe",
        type=_timeframe,
        metavar="LENGTH",
        help="the length of a candle, like 30m, 1h or 1d; needed with --labels close, refused "
        "with --labels open",
    )


def _add_signals(parser: argparse.ArgumentParser) -> None:
    signals = parser.add_argument_group("signals")
    signals.add_argument(
        "--model", metavar="NAME", help="backtest only this model's predictions (column model)"
    )
    signals.add_argument(
        "--allow-gaps",
        action="store_true",
        help="drop predictions without a candle and let candles without a prediction repeat "
        "the previous one, instead of refusing both; run.json counts them",
    )


def add_post_processing(parser: argparse.ArgumentParser, *, grid: bool) -> None:
    """Adds the post-processing options as one group, in the order of the steps. With ``grid``
    the rule's limit is run-all's ``--thresholds``, a list, instead of ``--threshold``."""
    steps = parser.add_argument_group(
        "post-processing",
        "the steps from the predictions to the signal, applied in this order; each is off "
        "unless given",
    )
    _add_before_the_rule(steps)
    _add_rule(steps, grid=grid)
    steps.add_argument("--long-only", action="store_true", help="flat instead of short")
    steps.add_argument(
        "--confirm",
        type=_at_least(1),
        metavar="CANDLES",
        help="count a value of the signal only once it has held for CANDLES rows in a row",
    )
    steps.add_argument(
        "--min-hold",
        type=_at_least(1),
        metavar="CANDLES",
        help="keep each new position for at least CANDLES rows",
    )


def _add_before_the_rule(steps: argparse._ArgumentGroup) -> None:
    steps.add_argument(
        "--calibrate",
        choices=["zscore", "rank"],
        help="rescale each prediction from the --calibration-window predictions ending at it: "
        "zscore in standard deviations from their mean, rank by its place among them, in "
        "[-1, 1]",
    )
    steps.add_argument(
        "--calibration-window",
        type=_at_least(2),
        metavar="N",
        help="how many predictions --calibrate rescales from, 2 or more; goes with --calibrate",
    )
    steps.add_argument(
        "--ema",
        type=_at_least(1),
        metavar="SPAN",
        help="smooth the predictions with an exponential moving average of this span, 1 or more",
    )


def _add_rule(steps: argparse._ArgumentGroup, *, grid: bool) -> None:
    steps.add_argument(
        "--rule",
        choices=["threshold", "hysteresis", "kmeans"],
        default="threshold",
        help="how a prediction becomes the signal: threshold (--threshold), hysteresis "
        "(--threshold to open a position, --exit to close it) or kmeans (--k, --kmeans-window, "
        "--refit-every) (default: threshold)",
    )
    _add_limit(steps, grid=grid)
    steps.add_argument(
        "--exit",
        type=_non_negative,
        metavar="LIMIT",
        help="with --rule hysteresis: a long closes at a prediction below LIMIT, a short above "
        "-LIMIT; at most --threshold",
    )
    steps.add_argument(
        "--k",
        type=int,
        choices=[2, 3, 4, 5],
        help="with --rule kmeans: the number of groups; long in the highest, short in the lowest",
    )
    steps.add_argument(
        "--kmeans-window",
        type=_at_least(2),
        metavar="N",
        help="with --rule kmeans: how many earlier predictions a fit uses, at least 2 * --k",
    )
    steps.add_argument(
        "--refit-every",
        type=_at_least(1),
        metavar="N",
        help="with --rule kmeans: how many rows a fit is used for, 1 or more",
    )


def _add_limit(steps: argparse._ArgumentGroup, *, grid: bool) -> None:
    if grid:
        steps.add_argument(
            "--thresholds",
            type=_list(_non_negative),
            metavar="LIMITS",
            help="comma-separated thresholds, each as run's --threshold (default: 0); with "
            "--rule hysteresis the limits a position opens at; refused with --rule kmeans",
        )
        return
    steps.add_argument(
        "--threshold",
        type=_non_negative,
        metavar="LIMIT",
        help="long at a prediction of LIMIT or more, short at -LIMIT or less, else flat "
        "(default: 0); with --rule hysteresis the limit a position opens at; refused with "
        "--rule kmeans",
    )


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
        "--stop-loss",
        type=_fraction,
        metavar="FRACTION",
        help="close a position once it loses this fraction of its entry price, 0.05 for 5%% "
        "(default: no stop)",
    )
    add_drawdown_stop(engine)
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


def add_drawdown_stop(engine: argparse._ArgumentGroup) -> None:
    """Adds ``--drawdown-stop`` (``Settings.drawdown_stop``) to the engine group."""
    engine.add_argument(
        "--drawdown-stop",
        type=_fraction,
        metavar="FRACTION",
        help="halt the run once the equity is this fraction below its highest level so far, "
        "0.2 for 20%% (default: no drawdown stop)",
    )


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    """Runs one backtest with the options in ``args`` and returns the exit code.

    A wrong option stops at ``parser.error`` (exit code 2). A missing or unreadable file, a
    missing or mistyped column or data the steps refuse prints the reason on one line and
    returns 2, without a traceback and without writing any file.
    """
    check_time_labels(args, parser)
    check_post_processing(args, parser, grid=False)
    try:
        values = _run(args)
    # The engine's InvalidInput is a ValueError; a Polars error is data no step checks for.
    except (OSError, ValueError, pl.exceptions.PolarsError) as error:
        reason = " ".join(str(error).split())
        sys.stderr.write(f"{parser.prog}: error: {reason}\n")
        return 2
    sys.stdout.write(_summary(values, args.out))
    return 0


def _run(args: argparse.Namespace) -> Stats:
    settings = Settings(
        fill=args.fill,
        stop_loss=args.stop_loss,
        drawdown_stop=args.drawdown_stop,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
    )
    post = post_processing(args, threshold=rule_limit(args.rule, args.threshold))
    candles = read_input(args.candles, "candles", args.ts_column, _PRICES)
    model = [] if args.model is None else ["model"]
    predictions = read_input(
        args.predictions, "predictions", args.ts_column, ["prediction", *model]
    )
    frame, report = aligned(
        candles,
        predictions,
        timeframe=args.timeframe,
        model=args.model,
        allow_gaps=args.allow_gaps,
        source=args.predictions,
    )
    result = backtest(frame.with_columns(make_signal(frame["prediction"], post)), settings)
    values = stats(result.trades, result.series, frame)
    _write(args.out, result, values, _record(args, settings, result, report, post=post))
    return values


def check_time_labels(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Stops at ``parser.error`` unless ``--timeframe`` comes exactly with ``--labels close``."""
    if args.labels == "close" and args.timeframe is None:
        parser.error("--labels close needs --timeframe, the length of a candle (30m, 1h, 1d)")
    if args.labels == "open" and args.timeframe is not None:
        parser.error("--timeframe goes only with --labels close: open labels are not moved")


# The post-processing: the steps between ``align`` and ``backtest``, in the order of
# docs/engine.md (Signals). Both commands take their options, apply and record them from here.

# The options of each rule (by their dest), and the ones it cannot do without: the limit
# defaults to 0.
_RULE_OPTIONS: dict[str, tuple[str, ...]] = {
    "threshold": ("threshold",),
    "hysteresis": ("threshold", "exit"),
    "kmeans": ("k", "kmeans_window", "refit_every"),
}
_RULE_NEEDS: dict[str, tuple[str, ...]] = {
    "threshold": (),
    "hysteresis": ("exit",),
    "kmeans": ("k", "kmeans_window", "refit_every"),
}


@dataclass(frozen=True, slots=True)
class PostProcessing:
    """The steps from the predictions to the signal, in the order ``make_signal`` applies
    them: calibration, ``ema``, one rule that makes the signal, ``long_only``, ``confirm``,
    ``min_hold``. A step that is None is skipped. Plain values only, so run-all can send it to
    its worker processes.

    Attributes:
        calibrate: ``zscore`` or ``rank`` from the ``calibration_window`` predictions ending
            at each one, or None.
        calibration_window: the window of ``calibrate``, 2 or more.
        ema: the span of the exponential moving average, 1 or more, or None.
        rule: ``threshold`` (its limit is ``threshold``), ``hysteresis`` (``threshold`` is the
            limit a position opens at, ``exit`` the one it closes below) or ``kmeans`` (``k``,
            ``kmeans_window``, ``refit_every``; ``threshold`` is None).
        long_only: flat instead of short.
        confirm: the rows a value must hold before it counts, or None.
        min_hold: the rows a new position is kept for, or None.
    """

    calibrate: Calibration | None = None
    calibration_window: int | None = None
    ema: int | None = None
    rule: Rule = "threshold"
    threshold: float | None = 0.0
    exit: float | None = None
    k: int | None = None
    kmeans_window: int | None = None
    refit_every: int | None = None
    long_only: bool = False
    confirm: int | None = None
    min_hold: int | None = None


def make_signal(predictions: pl.Series, post: PostProcessing) -> pl.Series:
    """The ``signal`` of the predictions after every step of ``post``, in their order.

    Raises:
        ValueError: a step refuses its argument or the predictions, or ``post`` lacks an
            argument its rule needs.
    """
    return decide(prepare(predictions, post), post)


def prepare(predictions: pl.Series, post: PostProcessing) -> pl.Series:
    """The steps before the rule: calibration, then ``ema``. Apart from ``make_signal`` so that
    run-all does them once per model: its thresholds change the rule alone."""
    if post.calibrate is not None:
        if post.calibration_window is None:
            raise ValueError("calibrate needs calibration_window")
        calibrate = zscore if post.calibrate == "zscore" else rank
        predictions = calibrate(predictions, post.calibration_window)
    if post.ema is not None:
        predictions = ema(predictions, post.ema)
    return predictions


def decide(predictions: pl.Series, post: PostProcessing) -> pl.Series:
    """The steps from the rule on: the rule, ``long_only``, ``confirm``, ``min_hold``."""
    signal = _rule(predictions, post)
    if post.long_only:
        signal = long_only(signal)
    if post.confirm is not None:
        signal = confirm(signal, post.confirm)
    if post.min_hold is not None:
        signal = min_hold(signal, post.min_hold)
    return signal


def _rule(predictions: pl.Series, post: PostProcessing) -> pl.Series:
    if post.rule == "kmeans":
        if post.k is None or post.kmeans_window is None or post.refit_every is None:
            raise ValueError("rule kmeans needs k, kmeans_window and refit_every")
        return kmeans(predictions, post.k, post.kmeans_window, post.refit_every)
    if post.threshold is None:
        raise ValueError(f"rule {post.rule} needs threshold")
    if post.rule == "hysteresis":
        if post.exit is None:
            raise ValueError("rule hysteresis needs exit")
        return hysteresis(predictions, post.threshold, post.exit)
    return threshold(predictions, post.threshold)


def describe(post: PostProcessing) -> dict[str, Any]:
    """The steps as ``run.json`` lists them under ``post_processing``: in their order, each
    with the arguments of its function, null when it is off."""
    rules = {
        "threshold": {"limit": post.threshold},
        "hysteresis": {"enter": post.threshold, "exit": post.exit},
        "kmeans": {"k": post.k, "window": post.kmeans_window, "refit_every": post.refit_every},
    }
    calibrate = {"name": post.calibrate, "window": post.calibration_window}
    return {
        "calibrate": None if post.calibrate is None else calibrate,
        "ema": None if post.ema is None else {"span": post.ema},
        "rule": {"name": post.rule, **rules[post.rule]},
        "long_only": post.long_only,
        "confirm": None if post.confirm is None else {"candles": post.confirm},
        "min_hold": None if post.min_hold is None else {"candles": post.min_hold},
    }


def post_processing(args: argparse.Namespace, *, threshold: float | None) -> PostProcessing:
    """The post-processing the options ask for, after ``check_post_processing``.
    ``threshold`` is the rule's limit (see ``rule_limit``; run-all gives each of its
    ``--thresholds`` in turn)."""
    return PostProcessing(
        calibrate=args.calibrate,
        calibration_window=args.calibration_window,
        ema=args.ema,
        rule=args.rule,
        threshold=threshold,
        exit=args.exit,
        k=args.k,
        kmeans_window=args.kmeans_window,
        refit_every=args.refit_every,
        long_only=args.long_only,
        confirm=args.confirm,
        min_hold=args.min_hold,
    )


def rule_limit(rule: Rule, given: float | None) -> float | None:
    """The rule's limit from ``--threshold``: 0 when not given; None with ``kmeans``, which
    has none."""
    if rule == "kmeans":
        return None
    return 0.0 if given is None else given


def check_post_processing(
    args: argparse.Namespace, parser: argparse.ArgumentParser, *, grid: bool
) -> None:
    """Stops at ``parser.error`` on a mix of post-processing options that makes no sense:
    ``--calibrate`` without ``--calibration-window`` or the other way round, an option of
    another rule than ``--rule``, a rule without an option it needs, an ``--exit`` above the
    limit a position opens at or a ``--kmeans-window`` under ``2 * --k``. With ``grid`` the
    limit is run-all's ``--thresholds``."""
    if (args.calibrate is None) != (args.calibration_window is None):
        parser.error(
            "--calibrate and --calibration-window go together: the method and how many "
            "predictions it rescales from"
        )
    _check_rule_options(args, parser, grid=grid)
    _check_rule_limits(args, parser, grid=grid)


def _check_rule_options(
    args: argparse.Namespace, parser: argparse.ArgumentParser, *, grid: bool
) -> None:
    def option(name: str) -> tuple[str, Any]:
        """The flag and the value of a rule option; run-all's limits are ``--thresholds``."""
        dest = f"{name}s" if grid and name == "threshold" else name
        return "--" + dest.replace("_", "-"), getattr(args, dest)

    names = [name for options in _RULE_OPTIONS.values() for name in options]
    for name in names:
        flag, value = option(name)
        if value is not None and name not in _RULE_OPTIONS[args.rule]:
            rules = " or ".join(rule for rule, taken in _RULE_OPTIONS.items() if name in taken)
            parser.error(f"{flag} goes only with --rule {rules}")
    missing = [option(name)[0] for name in _RULE_NEEDS[args.rule] if option(name)[1] is None]
    if missing:
        parser.error(f"--rule {args.rule} needs {_and(missing)}")


def _check_rule_limits(
    args: argparse.Namespace, parser: argparse.ArgumentParser, *, grid: bool
) -> None:
    if args.rule == "hysteresis":
        flag = "--thresholds" if grid else "--threshold"
        given = args.thresholds if grid else args.threshold
        enters = (0.0,) if given is None else (tuple(given) if grid else (given,))
        for enter in enters:
            if args.exit > enter:
                parser.error(
                    f"--exit must be at most {flag}, the limit a position opens at: got "
                    f"--exit {args.exit} and {flag} {enter}"
                )
    if args.rule == "kmeans" and args.kmeans_window < 2 * args.k:
        parser.error(
            f"--kmeans-window must be at least 2 * --k ({2 * args.k}), got {args.kmeans_window}"
        )


def _and(items: list[str]) -> str:
    """``a``, ``a and b`` or ``a, b and c``."""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def aligned(
    candles: pl.DataFrame,
    predictions: pl.DataFrame,
    *,
    timeframe: int | None,
    model: str | None,
    allow_gaps: bool,
    source: Path,
) -> tuple[pl.DataFrame, AlignReport]:
    """The candles from the model's first to its last prediction, with ``prediction``.

    Both frames have ``ts`` (see ``read_input``). A ``timeframe`` in seconds means both are
    labelled by the candle's close: ``relabel`` moves them back by it first. ``allow_gaps``
    aligns with ``strict=False``. ``source`` is the predictions file, for the messages.

    Raises:
        ValueError: the file holds several models and ``model`` is None, or ``relabel`` or
            ``align`` refuses the data; a refused gap points to ``--allow-gaps``.
    """
    models = predictions["model"].n_unique() if "model" in predictions.columns else 1
    if model is None and models > 1:
        raise ValueError(
            f"The predictions file {source} holds {models} models: pick one with --model"
        )
    if timeframe is not None:
        candles = relabel(candles, timeframe)
        predictions = relabel(predictions, timeframe)
    try:
        return align(candles, predictions, model=model, strict=not allow_gaps)
    except ValueError as error:
        raise ValueError(str(error).replace("pass strict=False", "pass --allow-gaps")) from None


def read_input(path: Path, what: str, ts_column: str, columns: list[str]) -> pl.DataFrame:
    """The Parquet file at ``path`` with its time column ``ts_column`` renamed to ``ts``.

    ``what`` names the file in the messages (``candles`` or ``predictions``).

    Raises:
        ValueError: there is no such file, it cannot be read as Parquet, a column is missing or
            the time column is not integer epoch seconds.
    """
    if not path.is_file():
        raise ValueError(f"No {what} file at {path}")
    try:
        frame = pl.read_parquet(path)
    except (OSError, pl.exceptions.PolarsError) as error:
        raise ValueError(f"Cannot read the {what} file {path} as Parquet: {error}") from error
    missing = [name for name in [ts_column, *columns] if name not in frame.columns]
    if missing:
        names = ", ".join(map(repr, missing))
        raise ValueError(f"The {what} file {path} has no column {names}")
    if ts_column != "ts" and "ts" in frame.columns:
        raise ValueError(
            f"The {what} file {path} has a 'ts' column besides {ts_column!r}: drop or rename it"
        )
    dtype = frame.schema[ts_column]
    if not dtype.is_integer():
        raise ValueError(
            f"Column {ts_column!r} of the {what} file {path} must be integer epoch seconds, "
            f"not {dtype}"
        )
    return frame.rename({ts_column: "ts"})


def _record(
    args: argparse.Namespace,
    settings: Settings,
    result: Result,
    report: AlignReport,
    *,
    post: PostProcessing,
) -> dict[str, Any]:
    """What ``run.json`` holds: enough to repeat the run and to tell whether its inputs
    changed."""
    return {
        "engine_version": result.engine_version,
        "inputs": {
            "candles": {"path": str(args.candles), "sha256": _sha256(args.candles)},
            "predictions": {"path": str(args.predictions), "sha256": _sha256(args.predictions)},
        },
        "settings": {
            "ts_column": args.ts_column,
            "labels": args.labels,
            "timeframe_seconds": args.timeframe,
            "model": args.model,
            "allow_gaps": args.allow_gaps,
            "threshold": post.threshold,
            "long_only": post.long_only,
            **settings.model_dump(),
        },
        "post_processing": describe(post),
        "align": dataclasses.asdict(report),
    }


def _sha256(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def _write(out: Path, result: Result, values: Stats, record: dict[str, Any]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    result.trades.write_parquet(out / "trades.parquet")
    result.series.with_columns(drawdown(result.series)).write_parquet(out / "series.parquet")
    _write_json(out / "stats.json", values)
    _write_json(out / "run.json", record)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """``data`` as indented JSON in its own key order, with LF line ends on every OS."""
    text = json.dumps(data, indent=2, allow_nan=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def _summary(values: Stats, out: Path) -> str:
    rows = [
        ("trades", values["num_trades"], "d"),
        ("win rate", values["win_rate"], ".2%"),
        ("total return", values["total_return"], ".2%"),
        ("max drawdown", values["max_drawdown"], ".2%"),
        ("sharpe", values["sharpe"], ".2f"),
        ("buy and hold", values["buy_and_hold_return"], ".2%"),
    ]
    lines = [
        f"Wrote trades.parquet, series.parquet, stats.json and run.json to {out}",
        *(
            f"  {name:<14}{'n/a' if value is None else format(value, spec)}"
            for name, value, spec in rows
        ),
    ]
    return "\n".join(lines) + "\n"


def _timeframe(text: str) -> int:
    """The seconds of a candle length like 30m, 1h or 1d (an argparse type)."""
    match = _TIMEFRAME.fullmatch(text)
    if match is None:
        raise argparse.ArgumentTypeError(f"not a candle length like 30m, 1h or 1d: {text!r}")
    return int(match[1]) * _UNIT_SECONDS[match[2]]


def _non_negative(text: str) -> float:
    """A finite number of 0 or more (an argparse type)."""
    value = _number(text)
    if value < 0:
        raise argparse.ArgumentTypeError(f"must be 0 or more, got {text}")
    return value


def _fraction(text: str) -> float:
    """A number between 0 and 1, both excluded (an argparse type)."""
    value = _number(text)
    if not 0 < value < 1:
        raise argparse.ArgumentTypeError(f"must be between 0 and 1 (0.05 is 5%), got {text}")
    return value


def _number(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}") from None
    if not math.isfinite(value):
        raise argparse.ArgumentTypeError(f"not a finite number: {text!r}")
    return value


def _at_least(minimum: int) -> Callable[[str], int]:
    """An argparse type: a whole number of ``minimum`` or more."""

    def parse(text: str) -> int:
        try:
            value = int(text)
        except ValueError:
            raise argparse.ArgumentTypeError(f"not a whole number: {text!r}") from None
        if value < minimum:
            raise argparse.ArgumentTypeError(f"must be {minimum} or more, got {text}")
        return value

    return parse


def _list[T](item: Callable[[str], T]) -> Callable[[str], tuple[T, ...]]:
    """An argparse type: comma-separated values, each of the type ``item``, none repeated."""

    def parse(text: str) -> tuple[T, ...]:
        values = tuple(item(part.strip()) for part in text.split(","))
        if len(set(values)) < len(values):
            raise argparse.ArgumentTypeError(f"a value repeats: {text!r}")
        return values

    return parse

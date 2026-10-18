"""The post-processing of ``candlestack-bt``: the steps between ``align`` and ``backtest``, in
the order of docs/engine.md (Signals): calibration (``zscore`` or ``rank``), ``ema``, one rule
that makes the signal (``threshold``, ``hysteresis`` or ``kmeans``), ``long_only``, ``confirm``,
``min_hold``. Both commands take their options (``add_post_processing``,
``check_post_processing``, ``post_processing``, ``rule_limit``), apply them (``make_signal``, or
``prepare`` and ``decide`` apart) and record them in ``run.json`` (``describe``) from here, so
the order cannot drift. ``add_drawdown_stop`` adds the engine's ``--drawdown-stop`` to both as
well.
"""

import argparse
from dataclasses import dataclass
from typing import Any, Literal

import polars as pl

from candlestack.cli.options import _at_least, _fraction, _list, _non_negative
from candlestack.signals import (
    confirm,
    ema,
    hysteresis,
    kmeans,
    long_only,
    min_hold,
    rank,
    threshold,
    zscore,
)

Calibration = Literal["zscore", "rank"]
Rule = Literal["threshold", "hysteresis", "kmeans"]

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


# The options


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
    limit = "each of --thresholds" if grid else "--threshold"
    steps.add_argument(
        "--exit",
        type=_non_negative,
        metavar="LIMIT",
        help="with --rule hysteresis: a long closes at a prediction below LIMIT, a short above "
        f"-LIMIT; at most {limit}",
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


def add_drawdown_stop(engine: argparse._ArgumentGroup) -> None:
    """Adds ``--drawdown-stop`` (``Settings.drawdown_stop``) to the engine group."""
    engine.add_argument(
        "--drawdown-stop",
        type=_fraction,
        metavar="FRACTION",
        help="halt the run once the equity is this fraction below its highest level so far, "
        "0.2 for 20%% (default: no drawdown stop)",
    )


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
    limit = "thresholds" if grid else "threshold"

    def option(name: str) -> tuple[str, Any]:
        """The flag and the value of a rule option; run-all's limits are ``--thresholds``."""
        dest = limit if name == "threshold" else name
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
        if given is None:
            enters = [(0.0, f"{flag} (default 0)")]
        elif grid:
            enters = [(enter, f"{flag} {enter}") for enter in given]
        else:
            enters = [(given, f"{flag} {given}")]
        for enter, where in enters:
            if args.exit > enter:
                parser.error(
                    f"--exit must be at most {flag}, the limit a position opens at: got "
                    f"--exit {args.exit} and {where}"
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

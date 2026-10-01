"""The statistics of one backtest run (``stats``) and its drawdown curve (``drawdown``).

Both read the engine's output (``trades`` and ``series``, see the engine's ``Result``) and the
candles it ran on. Returns are fractions (0.05 is 5%) and equity starts at 1.0.
"""

import itertools
import math
import statistics
from typing import Any

import polars as pl

# Epoch seconds have no leap seconds, so ts // _DAY is the UTC date of a candle.
_DAY = 86_400


def _drawdown() -> pl.Expr:
    """``equity / peak - 1``, where ``peak`` is the running max of equity, starting at 1.0."""
    peak = pl.max_horizontal(pl.col("equity").cum_max(), pl.lit(1.0))
    return pl.col("equity") / peak - 1


def drawdown(series: pl.DataFrame) -> pl.Series:
    """How far the equity of each row of a run's ``series`` is below its highest level so far.

    ``drawdown[t] = equity[t] / max(1.0, equity[0], ..., equity[t]) - 1``: 0 at a new high,
    -0.2 at 20% below it. The starting capital 1.0 is the first peak, so a run that loses from
    its start is in drawdown from its first row.

    Args:
        series: The engine's series, in time order; only ``equity`` is read.

    Returns:
        A Float64 series named ``drawdown`` with one value per row of ``series``.
    """
    return series.select(_drawdown().alias("drawdown")).to_series()


def stats(
    trades: pl.DataFrame,
    series: pl.DataFrame,
    candles: pl.DataFrame,
    periods_per_year: float = 252,
) -> dict[str, float | int | None]:
    """The statistics of one run, by name, always in the order below.

    Daily returns ``r``: the day of a row is the UTC date of its ``ts``, ``E[d]`` is the equity
    of the last row of day ``d``, and ``r[d] = E[d] / E[d-1] - 1``, the first day's from the
    starting capital ``E[0] = 1.0``. Days without rows are skipped; the risk-free rate is 0.

    - ``total_return = equity[last] - 1``.
    - ``max_drawdown = -min(drawdown(series)) = max(1 - equity[t] / peak[t])`` with
      ``peak[t] = max(1.0, equity[0], ..., equity[t])``: a positive fraction, 0 when equity
      never falls below a peak.
    - ``sharpe = mean(r) / std(r) * sqrt(periods_per_year)``, ``std`` with ddof 1.
    - ``sortino = mean(r) / sqrt(mean(min(r, 0) ** 2)) * sqrt(periods_per_year)``: the
      downside deviation (target 0) over all days is the denominator.
    - ``num_trades``: the rows of ``trades``, the ``end`` trade on the last candle included.
    - ``win_rate = count(return > 0) / num_trades``: a trade that returns exactly 0 is no win.
    - ``avg_trade_return = mean(return)``, ``best_trade_return = max(return)``,
      ``worst_trade_return = min(return)``, over the trades' ``return``.
    - ``exposure = count(position != 0) / rows of series``: the share of candles that close
      with a position open, long or short.
    - ``fees_paid = sum(fees)``: the trades' costs as fractions of capital, 0 without trades.
    - ``buy_and_hold_return = close[last] / close[first] - 1`` over the candles whose ``ts`` is
      in ``series``, i.e. holding the asset over the same candles as the run.

    A value that is undefined is None, never NaN, so the result is valid JSON: ``win_rate`` and
    the average, best and worst trade when there are no trades; ``sharpe`` and ``sortino`` with
    fewer than 2 days, when their denominator is 0 (``sortino`` of a run without a losing day)
    or once equity has reached 0 (a day that starts from 0 has no return); the values from
    ``series`` when it has no rows; and any value that would come out infinite or NaN.

    Args:
        trades: The engine's trades; ``return`` and ``fees`` are read.
        series: The engine's series, in time order; ``ts``, ``position`` and ``equity`` are
            read.
        candles: The candles of the run, at least the rows of ``series``; ``ts`` and ``close``
            are read.
        periods_per_year: Days per year that scale Sharpe and Sortino to a year: 252 trading
            days for stocks, 365 for crypto.

    Returns:
        ``total_return``, ``max_drawdown``, ``sharpe``, ``sortino``, ``num_trades`` (an int),
        ``win_rate``, ``avg_trade_return``, ``best_trade_return``, ``worst_trade_return``,
        ``exposure``, ``fees_paid`` and ``buy_and_hold_return`` (floats or None).
    """
    curve = series.select(
        total_return=pl.col("equity").last() - 1,
        max_drawdown=0.0 - _drawdown().min(),  # 0.0 - 0.0 is 0.0, where -(0.0) is -0.0
        exposure=(pl.col("position") != 0).mean(),
    ).row(0, named=True)
    deals = trades.select(
        num_trades=pl.len(),
        win_rate=(pl.col("return") > 0).mean(),
        avg_trade_return=pl.col("return").mean(),
        best_trade_return=pl.col("return").max(),
        worst_trade_return=pl.col("return").min(),
        fees_paid=pl.col("fees").sum(),
    ).row(0, named=True)
    returns = _daily_returns(series)
    values = {
        "total_return": curve["total_return"],
        "max_drawdown": curve["max_drawdown"],
        "sharpe": _sharpe(returns, periods_per_year),
        "sortino": _sortino(returns, periods_per_year),
        "num_trades": deals["num_trades"],
        "win_rate": deals["win_rate"],
        "avg_trade_return": deals["avg_trade_return"],
        "best_trade_return": deals["best_trade_return"],
        "worst_trade_return": deals["worst_trade_return"],
        "exposure": curve["exposure"],
        "fees_paid": deals["fees_paid"],
        "buy_and_hold_return": _buy_and_hold_return(series, candles),
    }
    return {name: _defined(value) for name, value in values.items()}


def _daily_returns(series: pl.DataFrame) -> list[float]:
    """``r[d] = E[d] / E[d-1] - 1`` for each UTC date that has rows, ``E[d]`` the equity of its
    last row and ``E[0] = 1.0``. Empty once equity has reached 0: no later day has a return."""
    ends = (
        series.group_by(pl.col("ts") // _DAY, maintain_order=True)
        .agg(pl.col("equity").last())
        .get_column("equity")
        .to_list()
    )
    days = list(itertools.pairwise([1.0, *ends]))
    if any(start == 0 for start, _ in days):
        return []
    return [end / start - 1 for start, end in days]


def _sharpe(returns: list[float], periods_per_year: float) -> float | None:
    """``mean(r) / std(r) * sqrt(periods_per_year)``, ddof 1; None under 2 days or std 0."""
    if len(returns) < 2:
        return None
    spread = statistics.stdev(returns)  # exact: identical returns give exactly 0
    if spread == 0:
        return None
    return statistics.fmean(returns) / spread * math.sqrt(periods_per_year)


def _sortino(returns: list[float], periods_per_year: float) -> float | None:
    """``mean(r) / sqrt(mean(min(r, 0) ** 2)) * sqrt(periods_per_year)``; None under 2 days or
    without a losing day."""
    if len(returns) < 2:
        return None
    downside = math.sqrt(statistics.fmean(min(r, 0.0) ** 2 for r in returns))
    if downside == 0:
        return None
    return statistics.fmean(returns) / downside * math.sqrt(periods_per_year)


def _buy_and_hold_return(series: pl.DataFrame, candles: pl.DataFrame) -> Any:
    """``close[last] / close[first] - 1`` over the candles whose ``ts`` is in ``series``;
    None when there are none."""
    held = candles.join(series.select("ts"), on="ts", how="semi").sort("ts")
    return held.select(pl.col("close").last() / pl.col("close").first() - 1).item()


def _defined(value: Any) -> Any:
    """``value``, or None when it is an infinite or NaN float: neither is a statistic, and
    JSON has neither."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value

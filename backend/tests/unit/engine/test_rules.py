"""The engine's rules on hand-made examples of 5-10 candles, the expected trades and series
worked out by hand. ``ts`` is the row number, so the times of a trade read as rows."""

from typing import Any

import polars as pl
import pytest

from candlestack.engine import Result, Settings, backtest

INPUT_SCHEMA = {
    "ts": pl.Int64,
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "signal": pl.Float64,
}
Candle = tuple[float, float, float, float, float]  # open, high, low, close, signal

CLOSE = Settings(fill="signal_close")
NEXT = Settings(fill="next_open")


def candles(*rows: Candle) -> pl.DataFrame:
    return pl.DataFrame(
        [(ts, *row) for ts, row in enumerate(rows)], schema=INPUT_SCHEMA, orient="row"
    )


def trade(
    signal_ts,
    open_ts,
    close_ts,
    side,
    open_price,
    close_price,
    reason,
    result,
    *,
    stop=None,
    fees=0.0,
    slippage_cost=0.0,
) -> dict[str, Any]:
    return {
        "signal_ts": signal_ts,
        "open_ts": open_ts,
        "close_ts": close_ts,
        "side": side,
        "open_price": open_price,
        "close_price": close_price,
        "stop_price": stop,
        "exit_reason": reason,
        "return": result,
        "fees": fees,
        "slippage_cost": slippage_cost,
    }


def check(
    result: Result, trades: list[dict[str, Any]], position: list[float], equity: list[float]
) -> None:
    # approx looks into one dict at a time, not into a list of them.
    assert result.trades.rows(named=True) == [pytest.approx(row, rel=1e-12) for row in trades]
    assert result.series["position"].to_list() == position
    assert result.series["equity"].to_list() == pytest.approx(equity, rel=1e-12)


LONG = candles(
    (100, 101, 99, 100, 0),
    (100, 102, 99, 101, 1),  # go long
    (102, 104, 101, 103, 1),
    (104, 106, 103, 105, 0),  # go flat
    (106, 107, 105, 106, 0),
    (106, 107, 105, 107, 0),
)


def test_signal_close_fills_a_long_at_the_close_of_the_signal_candle() -> None:
    check(
        backtest(LONG, CLOSE),
        [trade(1, 1, 3, 1, 101, 105, "signal", 105 / 101 - 1)],
        position=[0, 1, 1, 0, 0, 0],
        equity=[1, 1, 103 / 101, 105 / 101, 105 / 101, 105 / 101],
    )


def test_next_open_fills_a_long_at_the_open_of_the_next_candle() -> None:
    check(
        backtest(LONG, NEXT),
        [trade(1, 2, 4, 1, 102, 106, "signal", 106 / 102 - 1)],
        position=[0, 0, 1, 1, 0, 0],
        equity=[1, 1, 103 / 102, 105 / 102, 106 / 102, 106 / 102],
    )


def test_next_open_is_the_default_fill() -> None:
    assert backtest(LONG, Settings()).trades.equals(backtest(LONG, NEXT).trades)


def test_short_loses_when_the_price_rises() -> None:
    frame = candles(
        (50, 51, 49, 50, 0),
        (50, 51, 49, 50, -1),  # go short
        (50, 53, 50, 52, -1),  # sold at the open, 50
        (52, 56, 52, 55, -1),
        (55, 56, 54, 55, 0),  # go flat
        (56, 57, 55, 56, 0),  # bought back at the open, 56
    )

    check(
        backtest(frame, NEXT),
        [trade(1, 2, 5, -1, 50, 56, "signal", -0.12)],
        position=[0, 0, -1, -1, -1, 0],
        equity=[1, 1, 0.96, 0.9, 0.9, 0.88],
    )


def test_a_low_that_touches_the_stop_exits_at_the_level() -> None:
    frame = candles(
        (100, 100, 100, 100, 0),
        (100, 101, 99, 100, 1),  # long at 100, stop 75
        (99, 100, 80, 90, 1),
        (90, 91, 75, 80, 1),  # the low touches 75: out at 75
        (80, 81, 79, 80, 1),  # the signal is still long, but that is no new decision
        (80, 81, 79, 81, 1),
    )

    check(
        backtest(frame, CLOSE.model_copy(update={"stop_loss": 0.25})),
        [trade(1, 1, 3, 1, 100, 75, "stop", -0.25, stop=75)],
        position=[0, 1, 1, 0, 0, 0],
        equity=[1, 1, 0.9, 0.75, 0.75, 0.75],
    )


def test_an_open_beyond_the_stop_exits_at_the_open() -> None:
    frame = candles(
        (100, 100, 100, 100, 0),
        (100, 101, 99, 100, -1),  # short at 100, stop 125
        (110, 120, 105, 115, -1),
        (130, 135, 128, 132, -1),  # opens above 125: out at the open, 130
        (132, 133, 131, 132, -1),
        (132, 133, 131, 130, 0),  # flat already
    )

    check(
        backtest(frame, CLOSE.model_copy(update={"stop_loss": 0.25})),
        [trade(1, 1, 3, -1, 100, 130, "gap", -0.3, stop=125)],
        position=[0, -1, -1, 0, 0, 0],
        equity=[1, 1, 0.85, 0.7, 0.7, 0.7],
    )


def test_the_stop_comes_before_the_signal_of_the_same_candle() -> None:
    frame = candles(
        (100, 100, 100, 100, 0),
        (100, 100, 100, 100, 1),  # long at 100, stop 75
        (70, 71, 60, 65, -1),  # gap out at 70, then short at the close, 65, stop 81.25
        (65, 66, 60, 62, -1),
        (62, 63, 61, 62, -1),  # still short at the end: bought back at the last close
    )

    check(
        backtest(frame, CLOSE.model_copy(update={"stop_loss": 0.25})),
        [
            trade(1, 1, 2, 1, 100, 70, "gap", -0.3, stop=75),
            trade(2, 2, 4, -1, 65, 62, "end", 3 / 65, stop=81.25),
        ],
        position=[0, 1, -1, -1, 0],
        equity=[1, 1, 0.7, 0.7 * (1 + 3 / 65), 0.7 * (1 + 3 / 65)],
    )


def test_a_flip_closes_and_opens_with_the_fee_on_both_legs() -> None:
    frame = candles(
        (100, 100, 100, 100, 0),
        (100, 101, 99, 100, 1),  # long at 100: fee 0.001 of the capital
        (100, 111, 99, 110, -1),  # out at 110 (fee 0.001 x 1.1), short at 110
        (110, 111, 99, 100, -1),
        (100, 101, 99, 99, 0),  # bought back at 99 (fee 0.001 x 0.9)
        (99, 100, 98, 99, 0),
    )
    long_return = 0.1 - 0.0021
    capital = 1 + long_return

    check(
        backtest(frame, CLOSE.model_copy(update={"fee_bps": 10})),
        [
            trade(1, 1, 2, 1, 100, 110, "signal", long_return, fees=0.0021),
            trade(2, 2, 4, -1, 110, 99, "signal", 0.1 - 0.0019, fees=0.0019),
        ],
        position=[0, 1, -1, -1, 0, 0],
        equity=[
            1,
            1 - 0.001,
            capital * (1 - 0.001),
            capital * (1 + 1 / 11 - 0.001),
            capital * (1 + 0.1 - 0.0019),
            capital * (1 + 0.1 - 0.0019),
        ],
    )


def test_slippage_moves_both_fills_of_a_short_against_it() -> None:
    frame = candles(
        (100, 100, 100, 100, 0),
        (100, 100, 100, 100, -1),
        (100, 101, 95, 96, -1),  # sold at 100 x (1 - 0.005) = 99.5
        (96, 97, 89, 90, 0),
        (90, 91, 89, 90, 0),  # bought back at 90 x (1 + 0.005) = 90.45
        (90, 91, 89, 90, 0),
    )
    fees = 0.001 * (1 + 90.45 / 99.5)
    result = 1 - 90.45 / 99.5 - fees
    slippage_cost = 90.45 / 99.5 - 90 / 100  # the return at 100 and 90, minus the actual one

    check(
        backtest(frame, NEXT.model_copy(update={"fee_bps": 10, "slippage_bps": 50})),
        [trade(1, 2, 4, -1, 99.5, 90.45, "signal", result, fees=fees, slippage_cost=slippage_cost)],
        position=[0, 0, -1, -1, 0, 0],
        equity=[
            1,
            1,
            1 - (96 / 99.5 - 1) - 0.001,
            1 - (90 / 99.5 - 1) - 0.001,
            1 + result,
            1 + result,
        ],
    )


def test_slippage_moves_the_stop_level_with_the_entry_price() -> None:
    frame = candles(
        (100, 100, 100, 100, 0),
        (100, 100, 100, 100, 1),  # long at 100 x 1.01 = 101: stop 75.75, not 75
        (90, 91, 75.5, 80, 1),  # the low reaches 75.75: out at 75.75 x 0.99 = 74.9925
        (80, 81, 79, 80, 1),
        (80, 81, 79, 80, 1),
    )

    check(
        backtest(frame, CLOSE.model_copy(update={"stop_loss": 0.25, "slippage_bps": 100})),
        # Without slippage: in at 100, out at the level, 75.75, -0.2425; so slippage cost 0.015.
        [trade(1, 1, 2, 1, 101, 74.9925, "stop", -0.2575, stop=75.75, slippage_cost=0.015)],
        position=[0, 1, 0, 0, 0],
        equity=[1, 100 / 101, 0.7425, 0.7425, 0.7425],
    )


@pytest.mark.parametrize("settings", [CLOSE, NEXT], ids=["signal_close", "next_open"])
def test_the_first_row_is_only_a_warm_up(settings: Settings) -> None:
    frame = candles(
        (10, 11, 9, 10, 1),  # long from the start: no decision
        (10, 11, 9, 11, 1),
        (11, 12, 10, 12, 1),
        (12, 13, 11, 12, 0),  # flat: nothing to close
        (12, 13, 11, 13, 0),
    )

    check(backtest(frame, settings), [], position=[0] * 5, equity=[1] * 5)


ONE_CANDLE = candles(
    (20, 21, 19, 20, 0),
    (20, 21, 19, 20, 0),
    (20, 22, 19, 21, 1),  # go long
    (22, 23, 21, 23, 0),  # go flat
    (24, 25, 23, 24, 0),
    (24, 25, 23, 24, 0),
)


def test_flat_long_flat_with_signal_close() -> None:
    check(
        backtest(ONE_CANDLE, CLOSE),
        [trade(2, 2, 3, 1, 21, 23, "signal", 23 / 21 - 1)],
        position=[0, 0, 1, 0, 0, 0],
        equity=[1, 1, 1, 23 / 21, 23 / 21, 23 / 21],
    )


def test_flat_long_flat_with_next_open() -> None:
    check(
        backtest(ONE_CANDLE, NEXT),
        [trade(2, 3, 4, 1, 22, 24, "signal", 24 / 22 - 1)],
        position=[0, 0, 0, 1, 0, 0],
        equity=[1, 1, 1, 23 / 22, 24 / 22, 24 / 22],
    )


def test_after_a_stop_only_the_next_change_opens_again() -> None:
    frame = candles(
        (100, 100, 100, 100, 0),
        (100, 100, 100, 100, 1),  # go long
        (100, 101, 99, 100, 1),  # long at 100, stop 75
        (90, 92, 70, 80, 1),  # out at 75
        (80, 85, 79, 84, 1),  # still long: no new decision
        (84, 85, 83, 84, 0),  # go flat: nothing to close
        (84, 85, 83, 84, 1),  # go long again
        (85, 90, 84, 88, 1),  # long at 85, stop 63.75; closed at the end, 88
    )

    check(
        backtest(frame, NEXT.model_copy(update={"stop_loss": 0.25})),
        [
            trade(1, 2, 3, 1, 100, 75, "stop", -0.25, stop=75),
            trade(6, 7, 7, 1, 85, 88, "end", 88 / 85 - 1, stop=63.75),
        ],
        position=[0, 0, 1, 0, 0, 0, 0, 0],
        equity=[1, 1, 1, 0.75, 0.75, 0.75, 0.75, 0.75 * 88 / 85],
    )


def test_next_open_fills_the_order_before_it_checks_the_stop() -> None:
    frame = candles(
        (100, 100, 100, 100, 0),
        (100, 100, 100, 100, 1),  # go long
        (100, 101, 99, 100, 1),  # long at 100, stop 75
        (100, 101, 99, 100, 0),  # go flat
        (70, 72, 69, 71, 0),  # the order fills at the open, 70: a signal exit, not a gap
        (71, 72, 70, 71, -1),  # go short
        (80, 101, 79, 90, -1),  # short at 80, stop 100: the high touches it on the entry candle
        (90, 91, 89, 90, -1),
    )

    check(
        backtest(frame, NEXT.model_copy(update={"stop_loss": 0.25})),
        [
            trade(1, 2, 4, 1, 100, 70, "signal", -0.3, stop=75),
            trade(5, 6, 6, -1, 80, 100, "stop", -0.25, stop=100),
        ],
        position=[0, 0, 1, 1, 0, 0, 0, 0],
        equity=[1, 1, 1, 1, 0.7, 0.7, 0.525, 0.525],
    )


FLIP_AT_THE_END = candles(
    (10, 10, 10, 10, 0),
    (10, 11, 9, 10, 1),  # go long
    (10, 12, 10, 11, 1),
    (11, 12, 11, 12, 1),
    (12, 13, 11, 12, -1),  # go short on the last row
)


def test_a_flip_on_the_last_row_only_closes_with_signal_close() -> None:
    check(
        backtest(FLIP_AT_THE_END, CLOSE),
        [trade(1, 1, 4, 1, 10, 12, "signal", 0.2)],
        position=[0, 1, 1, 1, 0],
        equity=[1, 1, 1.1, 1.2, 1.2],
    )


def test_a_flip_on_the_last_row_is_never_filled_with_next_open() -> None:
    check(
        backtest(FLIP_AT_THE_END, NEXT),
        [trade(1, 2, 4, 1, 10, 12, "end", 0.2)],
        position=[0, 0, 1, 1, 0],
        equity=[1, 1, 1.1, 1.2, 1.2],
    )


@pytest.mark.parametrize("settings", [CLOSE, NEXT], ids=["signal_close", "next_open"])
def test_a_change_on_the_last_row_opens_nothing(settings: Settings) -> None:
    frame = candles(
        (10, 10, 10, 10, 0),
        (10, 11, 9, 10, 0),
        (10, 12, 10, 11, 0),
        (11, 12, 11, 12, 0),
        (12, 13, 11, 12, 1),  # go long on the last row
    )

    check(backtest(frame, settings), [], position=[0] * 5, equity=[1] * 5)


def test_an_open_position_closes_at_the_last_close() -> None:
    frame = candles(
        (10, 10, 10, 10, 0),
        (10, 11, 9, 10, -1),  # go short
        (10, 11, 9, 9, -1),  # short at 10
        (9, 10, 8, 8, -1),
        (8, 9, 7, 8, -1),  # bought back at the last close, 8; the last row is flat
    )

    check(
        backtest(frame, NEXT),
        [trade(1, 2, 4, -1, 10, 8, "end", 0.2)],
        position=[0, 0, -1, -1, 0],
        equity=[1, 1, 1.1, 1.2, 1.2],
    )


def test_fees_and_slippage_cost_are_the_return_without_costs_minus_the_return() -> None:
    frame = candles(
        (100, 100, 100, 100, 0),
        (100, 100, 100, 100, 1),  # long at 100 x 1.002 = 100.2
        (110, 111, 109, 110, 1),
        (110, 111, 109, 110, 1),  # still long at the end: out at 110 x 0.998 = 109.78
    )

    [row] = backtest(
        frame, CLOSE.model_copy(update={"fee_bps": 5, "slippage_bps": 20})
    ).trades.rows(named=True)

    assert row["fees"] == pytest.approx(0.0005 * (1 + 109.78 / 100.2), rel=1e-12)
    assert row["slippage_cost"] == pytest.approx(1.1 - 109.78 / 100.2, rel=1e-12)
    assert row["fees"] + row["slippage_cost"] == pytest.approx(0.1 - row["return"], rel=1e-12)


def test_the_end_leg_pays_its_fee() -> None:
    frame = candles(
        (10, 10, 10, 10, 0),
        (10, 11, 9, 10, 1),  # go long
        (10, 11, 9, 11, 1),  # long at 10: fee 0.001 of the capital
        (11, 12, 10, 12, 1),  # out at the last close, 12: fee 0.001 x 1.2
    )

    check(
        backtest(frame, NEXT.model_copy(update={"fee_bps": 10})),
        [trade(1, 2, 3, 1, 10, 12, "end", 0.2 - 0.0022, fees=0.0022)],
        position=[0, 0, 1, 0],
        equity=[1, 1, 1 + 0.1 - 0.001, 1 + 0.2 - 0.0022],
    )


@pytest.mark.parametrize(("low", "stopped"), [(75, True), (75.5, False)], ids=["75", "75.5"])
def test_a_next_open_entry_candle_whose_low_only_touches_the_stop_exits(
    low: float, stopped: bool
) -> None:
    frame = candles(
        (100, 100, 100, 100, 0),
        (100, 100, 100, 100, 1),  # go long
        (100, 101, low, 90, 1),  # long at the open, 100, stop 75
        (90, 91, 89, 90, 1),
    )

    result = backtest(frame, NEXT.model_copy(update={"stop_loss": 0.25}))

    if stopped:
        check(
            result,
            [trade(1, 2, 2, 1, 100, 75, "stop", -0.25, stop=75)],
            position=[0, 0, 0, 0],
            equity=[1, 1, 0.75, 0.75],
        )
    else:
        check(
            result,
            [trade(1, 2, 3, 1, 100, 90, "end", -0.1, stop=75)],
            position=[0, 0, 1, 0],
            equity=[1, 1, 0.9, 0.9],
        )


def test_a_next_open_order_from_the_row_before_the_last_can_stop_out_on_the_last_row() -> None:
    frame = candles(
        (10, 10, 10, 10, 0),
        (10, 10, 10, 10, 0),
        (10, 10, 10, 10, 1),  # go long on the row before the last
        (10, 11, 7, 9, 1),  # long at the open, 10, stop 7.5: the low reaches it
    )

    check(
        backtest(frame, NEXT.model_copy(update={"stop_loss": 0.25})),
        [trade(2, 3, 3, 1, 10, 7.5, "stop", -0.25, stop=7.5)],
        position=[0, 0, 0, 0],
        equity=[1, 1, 1, 0.75],
    )


@pytest.mark.parametrize("close", [20, 21])
def test_a_position_worth_nothing_at_a_close_is_ruined_and_nothing_opens_again(
    close: float,
) -> None:
    frame = candles(
        (10, 10, 10, 10, 0),
        (10, 10, 10, 10, -1),  # go short
        (10, 16, 10, 15, -1),  # short at 10: worth 0.5 at the close
        (15, 22, 15, close, -1),  # the price doubles: worth 0 (or less) at the close
        (21, 21, 20, 20, 1),  # go long: the order would fill on the next open
        (20, 21, 19, 21, 1),
        (21, 22, 20, 22, 1),
    )

    check(
        backtest(frame, NEXT),
        [trade(1, 2, 3, -1, 10, close, "ruin", 1 - close / 10)],
        position=[0, 0, -1, 0, 0, 0, 0],
        equity=[1, 1, 0.5, 0, 0, 0, 0],
    )


def test_a_gap_that_loses_more_than_the_capital_leaves_nothing() -> None:
    frame = candles(
        (10, 10, 10, 10, 0),
        (10, 10, 10, 10, -1),  # short at 10, stop 15
        (25, 26, 24, 25, -1),  # opens at 25: out at the open, a return of -1.5
        (25, 26, 24, 25, 0),
        (25, 26, 24, 25, -1),  # go short again: nothing opens
        (25, 26, 24, 24, -1),
    )

    check(
        backtest(frame, CLOSE.model_copy(update={"stop_loss": 0.5})),
        [trade(1, 1, 2, -1, 10, 25, "gap", -1.5, stop=15)],
        position=[0, -1, 0, 0, 0, 0],
        equity=[1, 1, 0, 0, 0, 0],
    )


def test_a_flip_whose_close_loses_the_whole_capital_opens_nothing() -> None:
    frame = candles(
        (10, 10, 10, 10, 0),
        (10, 10, 10, 10, -1),  # short at 10
        (12, 13, 11, 12, -1),
        (12, 20, 12, 20, 1),  # flip at the close, 20: the short returns -1
        (20, 21, 19, 21, 1),
        (21, 22, 20, 22, 0),
    )

    check(
        backtest(frame, CLOSE),
        [trade(1, 1, 3, -1, 10, 20, "signal", -1.0)],
        position=[0, -1, -1, 0, 0, 0],
        equity=[1, 1, 0.8, 0, 0, 0],
    )

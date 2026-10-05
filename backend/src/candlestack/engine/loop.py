"""The loop: one pass over the candles with at most one position, always fully invested.

The rules, the same for both fills:

1. Only a change of the signal is a decision; the first row just sets the starting signal.
2. ``signal_close`` fills a decision at the close of its candle, ``next_open`` at the open of
   the next candle. There the order fills first, then the stop of the position left is checked.
3. A flip (+1 to -1 or back) is a close and an open: two legs, each with its costs.
4. The stop level comes from the actual entry price: ``entry * (1 - side * stop_loss)``. On a
   candle the position held at its open, an open at or beyond the level exits at that open
   (``gap``); otherwise a low (long) or high (short) at or beyond it exits at the level
   (``stop``). On its entry candle a ``next_open`` position can only touch the level; a
   ``signal_close`` one is first checked on the next candle. The stop comes before the signal
   of the same candle, and after a stop only the next change opens a position again.
5. Slippage ``s`` moves each fill against the trade: an entry to ``price * (1 + side * s)``,
   an exit to ``price * (1 - side * s)``, a stop exit from its level. The fee is ``fee_bps``
   of each leg's notional: the capital on entry, the position's value on exit. A trade's
   return is capital after / capital before - 1, so
   ``side * (exit / entry - 1) - fee * (1 + exit / entry)``. Its slippage cost is the return
   with the prices before slippage minus that return, the same fees in both:
   ``side * (price_exit / price_entry - exit / entry)``.
6. A change on the last row opens nothing (with ``signal_close`` it may still close); a
   ``next_open`` order from the row before still fills at the last open, and the stop is
   checked on the last row. A position still open is closed at the last close (``end``).
7. Capital starts at 1.0 and compounds. A candle's equity is the capital after all its fills
   with the open position marked at its close (its exit costs not paid yet); its position is
   the side held after them, so the last row is flat.
8. Ruin: a position whose equity, marked at a candle's close, is at or below 0 closes at that
   close (``ruin``), and a trade whose return is at or below -1 leaves nothing. Either way the
   capital becomes 0, no position opens again and every later equity is 0.
"""

from candlestack.engine.inputs import Candles
from candlestack.engine.settings import Settings

# signal_ts, open_ts, close_ts, side, open_price, close_price, stop_price, exit_reason, return,
# fees, slippage_cost: the columns of Result.trades.
TradeRow = tuple[int, int, int, int, float, float, float | None, str, float, float, float]

_BPS = 1e-4


class Loop:
    """Runs the rules over ``candles`` once (``run``) and keeps what they produced: ``trades``
    (one ``TradeRow`` per closed trade) and per candle ``position`` and ``equity``."""

    def __init__(self, candles: Candles, settings: Settings) -> None:
        self.candles = candles
        self.next_open = settings.fill == "next_open"
        self.stop_loss = settings.stop_loss
        self.fee = settings.fee_bps * _BPS
        self.slippage = settings.slippage_bps * _BPS
        self.capital = 1.0  # after the closed trades
        self.ruined = False  # rule 8: the capital is 0 and nothing opens again
        self.side = 0
        self.signal_row = 0
        self.entry_row = 0
        self.entry_quote = 0.0  # the entry's fill price before slippage
        self.entry_price = 0.0  # and with it
        self.stop: float | None = None  # the level, set while a position with a stop is open
        self.trades: list[TradeRow] = []
        self.position: list[float] = []
        self.equity: list[float] = []

    def run(self) -> None:
        candles = self.candles
        last = len(candles.ts) - 1
        pending: int | None = None  # a next_open order, filled at the open of the next row
        # Starting from the first signal makes the first row a warm-up: it cannot be a change.
        previous = candles.signals[0] if candles.signals else 0
        for row, signal in enumerate(candles.signals):
            if self.ruined:
                self.position.append(0.0)
                self.equity.append(0.0)
                continue
            if pending is not None:
                self._fill(row, row - 1, candles.opens[row], pending)
                pending = None
            if self.stop is not None:
                self._check_stop(row, self.stop)
            if signal != previous:
                pending = self._decide(row, signal, last)
            previous = signal
            self._mark(row)
        if self.side:
            self._close(last, candles.closes[last], "end")
            self.position[last] = 0.0
            self.equity[last] = self.capital

    def _decide(self, row: int, signal: int, last: int) -> int | None:
        """Acts on a change of the signal on ``row``; returns the order left for the next open
        (one left on the last row is never filled)."""
        if self.next_open:
            return signal
        self._fill(row, row, self.candles.closes[row], signal, may_open=row < last)
        return None

    def _fill(
        self, row: int, signal_row: int, price: float, signal: int, *, may_open: bool = True
    ) -> None:
        """Moves the position to ``signal`` at ``price``: closes one on the other side or
        flat, then opens one on the signal's side unless the close ruined the capital."""
        if self.side and self.side != signal:
            self._close(row, price, "signal")
        if signal and not self.side and may_open and not self.ruined:
            self._open(row, signal_row, price, signal)

    def _check_stop(self, row: int, level: float) -> None:
        candles = self.candles
        if row > self.entry_row and self._beyond(candles.opens[row], level):
            self._close(row, candles.opens[row], "gap")
        elif self._beyond(candles.lows[row] if self.side > 0 else candles.highs[row], level):
            self._close(row, level, "stop")

    def _beyond(self, price: float, level: float) -> bool:
        """Whether ``price`` reached the stop ``level`` of the open position; touching counts."""
        return price <= level if self.side > 0 else price >= level

    def _open(self, row: int, signal_row: int, price: float, side: int) -> None:
        self.side = side
        self.signal_row = signal_row
        self.entry_row = row
        self.entry_quote = price
        self.entry_price = price * (1.0 + side * self.slippage)
        if self.stop_loss is not None:
            self.stop = self.entry_price * (1.0 - side * self.stop_loss)

    def _close(self, row: int, price: float, reason: str) -> None:
        side = self.side
        exit_price = price * (1.0 - side * self.slippage)
        growth = exit_price / self.entry_price  # exit notional per unit of entry notional
        fees = self.fee * (1.0 + growth)
        result = side * (growth - 1.0) - fees
        slippage_cost = side * (price / self.entry_quote - growth)
        ts = self.candles.ts
        self.trades.append(
            (
                ts[self.signal_row],
                ts[self.entry_row],
                ts[row],
                side,
                self.entry_price,
                exit_price,
                self.stop,
                reason,
                result,
                fees,
                slippage_cost,
            )
        )
        self.side = 0
        self.stop = None
        if result <= -1.0:
            self._ruin()
        else:
            self.capital *= 1.0 + result

    def _ruin(self) -> None:
        self.capital = 0.0
        self.ruined = True

    def _mark(self, row: int) -> None:
        equity = self.capital
        if self.side:
            close = self.candles.closes[row]
            equity *= 1.0 + self.side * (close / self.entry_price - 1.0) - self.fee
            if equity <= 0.0:
                # Closing costs at least as much as the mark, so the return is at most -1;
                # the capital is set to 0 here too, whatever the rounding of the return.
                self._close(row, close, "ruin")
                self._ruin()
                equity = 0.0
        self.position.append(float(self.side))
        self.equity.append(equity)

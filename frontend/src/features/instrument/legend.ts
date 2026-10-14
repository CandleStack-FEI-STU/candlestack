import { formatCompact, formatPriceWith, formatSignedChange } from '@/lib/numbers';

import type { Bar } from './bars';

// What the legend above the chart shows for one candle, ready to print, written like the
// instrument list writes them (src/lib/numbers.ts).
export type Legend = {
  open: string;
  high: string;
  low: string;
  close: string;
  change: string;
  volume: string;
  // Colored like its candle: green when it closed at or above its open.
  up: boolean;
};

// The candle under the cursor, or the newest one when the cursor is off the candles. The change
// is against the previous candle's close, like TradingView; the first candle has nothing before
// it, so its own open.
export function legendFor(bars: readonly Bar[], index: number | null, decimals: number): Legend | null {
  const at = index !== null && index >= 0 && index < bars.length ? index : bars.length - 1;
  const bar = bars[at];
  if (!bar) return null;
  const base = bars[at - 1]?.close ?? bar.open;
  const price = (value: number) => formatPriceWith(value, decimals);
  return {
    open: price(bar.open),
    high: price(bar.high),
    low: price(bar.low),
    close: price(bar.close),
    change: formatSignedChange(base === 0 ? 0 : ((bar.close - base) / base) * 100),
    volume: formatCompact(bar.volume),
    up: bar.close >= bar.open,
  };
}

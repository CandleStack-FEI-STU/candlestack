import type { Bar } from './bars';

// What the legend above the chart shows for one candle, ready to print.
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

// Decimals for a price: cents from 1 up (334.20), four significant digits below that, so a
// cheap coin does not read 0.00 (0.0001234).
export function priceDecimals(price: number): number {
  const abs = Math.abs(price);
  if (!Number.isFinite(abs) || abs === 0 || abs >= 1) return 2;
  return Math.min(10, 3 - Math.floor(Math.log10(abs)));
}

const volumeFormat = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 2 });

// 1234567 -> "1.23M", 7.67 -> "7.67".
export function formatVolume(volume: number): string {
  return volumeFormat.format(volume);
}

// -0.0004 % would print as "-0.00%"; anything that rounds to zero is "0.00%".
function formatChange(percent: number): string {
  if (Math.abs(percent) < 0.005) return '0.00%';
  return `${percent > 0 ? '+' : ''}${percent.toFixed(2)}%`;
}

// The candle under the cursor, or the newest one when the cursor is off the candles. The change
// is against the previous candle's close, like TradingView; the first candle has nothing before
// it, so its own open.
export function legendFor(bars: readonly Bar[], index: number | null, decimals: number): Legend | null {
  const at = index !== null && index >= 0 && index < bars.length ? index : bars.length - 1;
  const bar = bars[at];
  if (!bar) return null;
  const base = bars[at - 1]?.close ?? bar.open;
  const price = (value: number) => value.toFixed(decimals);
  return {
    open: price(bar.open),
    high: price(bar.high),
    low: price(bar.low),
    close: price(bar.close),
    change: formatChange(base === 0 ? 0 : ((bar.close - base) / base) * 100),
    volume: formatVolume(bar.volume),
    up: bar.close >= bar.open,
  };
}

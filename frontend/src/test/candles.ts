import type { Candles } from '@/api';

// A page of candles as the API sends it. `start` is where the API began counting (the first
// candle unless it is missing), `end` where the page ends; open, high, low and close are the
// time plus 0.1, 0.2, 0.3 and 0.4.
export function candles(times: readonly number[], page: { start?: number; end?: number; gaps?: number } = {}): Candles {
  const start = page.start ?? times[0] ?? 0;
  const end = page.end ?? (times.at(-1) ?? start) + 1;
  return {
    meta: {
      instrument: 'crypto:BTCUSDT',
      timeframe: '1m',
      start,
      end,
      source: 'binance',
      feed: 'spot',
      fingerprint: 'x',
      count: times.length,
      gaps: [],
      gaps_total: page.gaps ?? 0,
    },
    t: [...times],
    o: times.map((t) => t + 0.1),
    h: times.map((t) => t + 0.2),
    l: times.map((t) => t + 0.3),
    c: times.map((t) => t + 0.4),
    v: times.map(() => 7),
  };
}

// `count` open times `step` seconds apart from `from` on.
export function times(from: number, count: number, step = 60): number[] {
  return Array.from({ length: count }, (_, i) => from + i * step);
}

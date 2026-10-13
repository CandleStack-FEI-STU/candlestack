import type { Candles } from '@/api';

// One candle as the chart takes it. `time` is the open time in epoch seconds.
export type Bar = { time: number; open: number; high: number; low: number; close: number; volume: number };

// The API answers in columns (t, o, h, l, c, v); the chart wants one object per candle.
export function toBars(candles: Candles): Bar[] {
  return candles.t.map((time, i) => ({
    time,
    open: candles.o[i] ?? Number.NaN,
    high: candles.h[i] ?? Number.NaN,
    low: candles.l[i] ?? Number.NaN,
    close: candles.c[i] ?? Number.NaN,
    volume: candles.v[i] ?? 0,
  }));
}

export type History = {
  bars: Bar[];
  // Where the next older page ends: the oldest candle shown, or the start of an empty page.
  nextEnd: number | undefined;
  gapsTotal: number;
};

// Pages come newest first; overlaps between pages are dropped, so the result is sorted by time
// with every time once. An older page that adds no candle (only the one it overlaps with) means
// the source has nothing before it: history ends there.
export function mergePages(pages: readonly Candles[]): History {
  const byTime = new Map<number, Bar>();
  let nextEnd: number | undefined;
  let gapsTotal = 0;
  for (const [index, page] of pages.entries()) {
    const bars = toBars(page);
    const known = byTime.size;
    for (const bar of bars) if (!byTime.has(bar.time)) byTime.set(bar.time, bar);
    gapsTotal += page.meta.gaps_total;
    if (index > 0 && bars.length > 0 && byTime.size === known) {
      nextEnd = undefined;
      break;
    }
    nextEnd = bars[0]?.time ?? page.meta.start;
  }
  const bars = [...byTime.values()].toSorted((a, b) => a.time - b.time);
  return { bars, nextEnd, gapsTotal };
}

// History before `availableFrom` does not exist; without it the source cannot say, so stop.
export function hasOlder(nextEnd: number | undefined, availableFrom: number | null): boolean {
  return nextEnd !== undefined && availableFrom !== null && nextEnd > availableFrom;
}

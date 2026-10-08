import { PAGE_SIZE, type Candles } from '@/api';

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

// Pages come newest first. Each keeps its newest PAGE_SIZE candles; overlaps between pages
// are dropped, so the result is sorted by time with every time once.
export function mergePages(pages: readonly Candles[]): History {
  const byTime = new Map<number, Bar>();
  let nextEnd: number | undefined;
  let gapsTotal = 0;
  for (const page of pages) {
    const bars = toBars(page).slice(-PAGE_SIZE);
    for (const bar of bars) if (!byTime.has(bar.time)) byTime.set(bar.time, bar);
    nextEnd = bars[0]?.time ?? page.meta.start;
    gapsTotal += page.meta.gaps_total;
  }
  const bars = [...byTime.values()].toSorted((a, b) => a.time - b.time);
  return { bars, nextEnd, gapsTotal };
}

// History before `availableFrom` does not exist; without it the source cannot say, so stop.
export function hasOlder(nextEnd: number | undefined, availableFrom: number | null): boolean {
  return nextEnd !== undefined && availableFrom !== null && nextEnd > availableFrom;
}

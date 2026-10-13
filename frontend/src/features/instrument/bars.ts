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
  // Where the next older page ends: where the oldest page begins.
  nextEnd: number | undefined;
  gapsTotal: number;
  // The latest page begins above `since`, so the older pages are left out and history goes on
  // from the latest page.
  detached: boolean;
};

// Pages come newest first, each one ending where the one before it begins (`meta.start`, the
// first candle the API counted, a missing one too). Overlaps are dropped, so the result is sorted
// by time with every time once. An older page whose start is not below its end has nothing
// before it: history ends there. The latest page reaches down to `since`, where the older pages
// end; when it was refreshed by limit instead (`pageRange`), the older pages are not joined to it.
export function mergePages(pages: readonly Candles[], since?: number): History {
  const detached = since !== undefined && (pages[0]?.meta.start ?? since) > since;
  const byTime = new Map<number, Bar>();
  let nextEnd: number | undefined;
  let gapsTotal = 0;
  for (const page of detached ? pages.slice(0, 1) : pages) {
    for (const bar of toBars(page)) if (!byTime.has(bar.time)) byTime.set(bar.time, bar);
    gapsTotal += page.meta.gaps_total;
    if (nextEnd !== undefined && page.meta.start >= nextEnd) {
      nextEnd = undefined;
      break;
    }
    nextEnd = page.meta.start;
  }
  const bars = [...byTime.values()].toSorted((a, b) => a.time - b.time);
  return { bars, nextEnd, gapsTotal, detached };
}

// History before `availableFrom` does not exist; without it the source cannot say, so stop.
export function hasOlder(nextEnd: number | undefined, availableFrom: number | null): boolean {
  return nextEnd !== undefined && availableFrom !== null && nextEnd > availableFrom;
}

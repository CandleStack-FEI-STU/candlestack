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
  // The latest page begins above `since`: the older pages are left out, so no hole shows, until
  // useCandleHistory drops them.
  detached: boolean;
};

const EMPTY: History = { bars: [], nextEnd: undefined, gapsTotal: 0, detached: false };

// The latest page, then the older pages, newest first; a page that has not arrived yet is
// undefined, and the pages below it wait for it. Each older page ends where the one before it
// begins (`meta.start`, the first candle the API counted, a missing one too). Overlaps are
// dropped, so the result is sorted by time with every time once. The API skips the time without
// sessions, so an older page without a candle has no data below it: history ends there. The
// latest page reaches down to `since`, where the older pages end; when it was refreshed by limit
// instead (`pageRange`), the older pages are not joined to it.
export function mergePages(pages: readonly (Candles | undefined)[], since?: number): History {
  const [latest, ...older] = pages;
  if (latest === undefined) return EMPTY;
  const detached = since !== undefined && latest.meta.start > since;
  const byTime = new Map<number, Bar>();
  const add = (page: Candles) => {
    for (const bar of toBars(page)) if (!byTime.has(bar.time)) byTime.set(bar.time, bar);
  };
  add(latest);
  let nextEnd: number | undefined = latest.meta.start;
  let gapsTotal = latest.meta.gaps_total;
  for (const page of detached ? [] : older) {
    if (page === undefined) break;
    add(page);
    gapsTotal += page.meta.gaps_total;
    if (page.t.length === 0) {
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

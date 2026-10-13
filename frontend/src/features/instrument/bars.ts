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
};

// Older pages in a row without a candle after which history ends. One or two are an outage of
// the source; more likely the data simply stops there, and asking on would cost a request each.
const EMPTY_PAGES = 3;

export type Pages = {
  // The latest page; undefined until it arrives.
  latest: Candles | undefined;
  // The older pages, newest first; undefined while one is on its way. The first ends at the
  // anchor, each next one where the one before it begins (`meta.start`, the first candle the
  // API counted, a missing one too).
  older: readonly (Candles | undefined)[];
  // The candles between the anchor and the start of the refreshed latest page, once it moved on.
  bridge?: Candles;
  // Where the older pages begin to hang: the start of the latest page when the first was asked.
  anchor?: number;
};

// The bars of all pages, sorted by time with every time once. An older page without a candle
// is an outage when the API still counted candles in it (its start is below its end): history
// goes on below it, up to EMPTY_PAGES in a row.
export function mergePages({ latest, older, bridge, anchor }: Pages): History {
  if (latest === undefined) return { bars: [], nextEnd: undefined, gapsTotal: 0 };
  const byTime = new Map<number, Bar>();
  let gapsTotal = 0;
  for (const page of [latest, bridge, ...older]) {
    if (page === undefined) continue;
    for (const bar of toBars(page)) if (!byTime.has(bar.time)) byTime.set(bar.time, bar);
    gapsTotal += page.meta.gaps_total;
  }
  const bars = [...byTime.values()].toSorted((a, b) => a.time - b.time);
  return { bars, nextEnd: chainEnd(latest, older, anchor), gapsTotal };
}

// Where the next older page ends, below the pages that arrived; undefined where history ends.
function chainEnd(latest: Candles, older: readonly (Candles | undefined)[], anchor: number | undefined) {
  let nextEnd = anchor ?? latest.meta.start;
  let empty = 0;
  for (const page of older) {
    if (page === undefined) break;
    empty = page.t.length === 0 ? empty + 1 : 0;
    if (empty === EMPTY_PAGES || page.meta.start >= nextEnd) return undefined;
    nextEnd = page.meta.start;
  }
  return nextEnd;
}

// Where the bridge ends: the start of the latest page once it moved on above the anchor, so the
// candles in between left it. Undefined while there is no gap.
export function bridgeTo(anchor: number | undefined, latest: Candles | undefined): number | undefined {
  const start = latest?.meta.start;
  return anchor !== undefined && start !== undefined && start > anchor ? start : undefined;
}

// History before `availableFrom` does not exist; without it the source cannot say, so stop.
export function hasOlder(nextEnd: number | undefined, availableFrom: number | null): boolean {
  return nextEnd !== undefined && availableFrom !== null && nextEnd > availableFrom;
}

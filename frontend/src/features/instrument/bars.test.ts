import { describe, expect, it } from 'vitest';

import { PAGE_SIZE, type Candles } from '@/api';

import { hasOlder, mergePages, toBars } from './bars';

// A page as the API sends it: `start` is where it begins, the first candle unless it is missing.
function page(times: number[], start = times[0] ?? 1000, gaps = 0): Candles {
  return {
    meta: {
      instrument: 'crypto:BTCUSDT',
      timeframe: '1h',
      start,
      end: (times.at(-1) ?? start) + 1,
      source: 'binance',
      feed: 'spot',
      fingerprint: 'x',
      count: times.length,
      gaps: [],
      gaps_total: gaps,
    },
    t: times,
    o: times.map((t) => t + 0.1),
    h: times.map((t) => t + 0.2),
    l: times.map((t) => t + 0.3),
    c: times.map((t) => t + 0.4),
    v: times.map(() => 7),
  };
}

// `count` candles one second apart from `from` on.
function times(from: number, count: number): number[] {
  return Array.from({ length: count }, (_, i) => from + i);
}

describe('toBars', () => {
  it('turns the columns into one object per candle', () => {
    expect(toBars(page([10, 20]))).toEqual([
      { time: 10, open: 10.1, high: 10.2, low: 10.3, close: 10.4, volume: 7 },
      { time: 20, open: 20.1, high: 20.2, low: 20.3, close: 20.4, volume: 7 },
    ]);
  });
});

describe('mergePages', () => {
  it('puts older pages before the latest one, sorted, and goes on where the oldest begins', () => {
    const history = mergePages([page([30, 40, 50]), page([10, 20], 5)], 30);
    expect(history.bars.map((bar) => bar.time)).toEqual([10, 20, 30, 40, 50]);
    expect(history.nextEnd).toBe(5);
    expect(history.detached).toBe(false);
  });

  it('keeps every candle of a page', () => {
    const history = mergePages([page(times(0, PAGE_SIZE + 20))]);
    expect(history.bars).toHaveLength(PAGE_SIZE + 20);
    expect(history.nextEnd).toBe(0);
  });

  it('leaves no hole when the latest page refreshes after the history below it was loaded', () => {
    // The latest page began at 1000, so the older page ends there. Much later, the latest page
    // refreshes from `since` (pageRange) and holds every candle from 1000 to now.
    const older = page(times(1000 - PAGE_SIZE, PAGE_SIZE));
    const refreshed = page(times(1000, PAGE_SIZE + 300));
    const history = mergePages([refreshed, older], 1000);
    expect(history.bars.map((bar) => bar.time)).toEqual(times(1000 - PAGE_SIZE, 2 * PAGE_SIZE + 300));
    expect(history.nextEnd).toBe(1000 - PAGE_SIZE);
  });

  it('drops the history below a latest page that no longer reaches it, instead of showing a hole', () => {
    // Idle too long for one request (pageRange): the latest page holds only its last candles,
    // which begin after the older page ends. History goes on from the latest page.
    const older = page(times(1000 - PAGE_SIZE, PAGE_SIZE));
    const refreshed = page(times(5000, PAGE_SIZE));
    const history = mergePages([refreshed, older], 1000);
    expect(history.bars.map((bar) => bar.time)).toEqual(times(5000, PAGE_SIZE));
    expect(history.nextEnd).toBe(5000);
    expect(history.detached).toBe(true);
  });

  it('ends history at an empty older page that starts where it ends', () => {
    // The API answers so when no candle opens before `end`; asking again would get the same.
    const history = mergePages([page([1000, 1001]), page([], 1000)], 1000);
    expect(history.bars.map((bar) => bar.time)).toEqual([1000, 1001]);
    expect(history.nextEnd).toBeUndefined();
    expect(hasOlder(history.nextEnd, 0)).toBe(false);
  });

  it('goes on before an older page whose candles are all missing', () => {
    const history = mergePages([page([1000, 1001]), page([], 400, 600)], 1000);
    expect(history.nextEnd).toBe(400);
    expect(history.gapsTotal).toBe(600);
  });

  it('adds up the gaps of every page and is empty without pages', () => {
    expect(mergePages([page([1], 1, 2), page([0], -10, 3)], 1).gapsTotal).toBe(5);
    expect(mergePages([])).toEqual({ bars: [], nextEnd: undefined, gapsTotal: 0, detached: false });
  });
});

describe('hasOlder', () => {
  it('stops at the first candle the source has, or when it cannot say', () => {
    expect(hasOlder(200, 100)).toBe(true);
    expect(hasOlder(100, 100)).toBe(false);
    expect(hasOlder(50, 100)).toBe(false);
    expect(hasOlder(200, null)).toBe(false);
    expect(hasOlder(undefined, 100)).toBe(false);
  });
});

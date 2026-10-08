import { describe, expect, it } from 'vitest';

import { PAGE_SIZE, type Candles } from '@/api';

import { hasOlder, mergePages, toBars } from './bars';

function page(times: number[], start = (times[0] ?? 1000) - 100, gaps = 0): Candles {
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

describe('toBars', () => {
  it('turns the columns into one object per candle', () => {
    expect(toBars(page([10, 20]))).toEqual([
      { time: 10, open: 10.1, high: 10.2, low: 10.3, close: 10.4, volume: 7 },
      { time: 20, open: 20.1, high: 20.2, low: 20.3, close: 20.4, volume: 7 },
    ]);
  });
});

describe('mergePages', () => {
  it('puts older pages before the latest one, sorted, without duplicates', () => {
    const history = mergePages([page([30, 40, 50]), page([10, 20, 30])]);
    expect(history.bars.map((bar) => bar.time)).toEqual([10, 20, 30, 40, 50]);
    expect(history.nextEnd).toBe(10);
  });

  it('keeps the newest PAGE_SIZE candles of a page', () => {
    const times = Array.from({ length: PAGE_SIZE + 20 }, (_, i) => i);
    const history = mergePages([page(times)]);
    expect(history.bars).toHaveLength(PAGE_SIZE);
    expect(history.nextEnd).toBe(20);
  });

  it('continues before an empty page from its start, so a long holiday does not stop history', () => {
    const history = mergePages([page([500, 600]), page([], 100)]);
    expect(history.nextEnd).toBe(100);
  });

  it('adds up the gaps of every page and is empty without pages', () => {
    expect(mergePages([page([1], 0, 2), page([0], -10, 3)]).gapsTotal).toBe(5);
    expect(mergePages([])).toEqual({ bars: [], nextEnd: undefined, gapsTotal: 0 });
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

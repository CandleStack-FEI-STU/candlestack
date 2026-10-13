import type { UseQueryResult } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';

import type { Candles } from '@/api';

import { summarize } from './useCandleHistory';

// A page that begins at its first candle, as a page asked for by limit does.
function candles(times: number[]): Candles {
  const start = times[0] ?? 0;
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
      gaps_total: 0,
    },
    t: times,
    o: times,
    h: times,
    l: times,
    c: times,
    v: times,
  };
}

// The parts of a query result that summarize reads.
function query(state: { data?: Candles; isFetching?: boolean; error?: Error }): UseQueryResult<Candles> {
  return {
    data: state.data,
    isFetching: state.isFetching ?? false,
    isPending: state.data === undefined,
    error: state.error ?? null,
    errorUpdatedAt: 0,
    dataUpdatedAt: state.data ? 1 : 0,
  } as UseQueryResult<Candles>;
}

describe('summarize', () => {
  it('waits for an older page on its way and reports one that failed', () => {
    const latest = query({ data: candles([1000, 1001]) });
    const loading = summarize([latest, query({ isFetching: true })], 1000);
    expect(loading.busy).toBe(true);
    expect(loading.olderBusy).toBe(true);
    expect(loading.nextEnd).toBeUndefined();
    const failed = query({ error: new Error('down') });
    expect(summarize([latest, failed], 1000).failed).toBe(failed);
  });

  it('lets the older pages below a detached latest page neither hold back nor fail loading', () => {
    // Refreshed after a long idle time, the latest page begins at 5000, far above the older
    // pages, which end at 1000; one of them is still loading, another failed.
    const latest = query({ data: candles([5000, 5001]) });
    const older = [
      query({ data: candles([998, 999]) }),
      query({ isFetching: true }),
      query({ error: new Error('down') }),
    ];
    const pages = summarize([latest, ...older], 1000);
    expect(pages.history.detached).toBe(true);
    expect(pages.history.bars.map((bar) => bar.time)).toEqual([5000, 5001]);
    expect(pages.busy).toBe(false);
    expect(pages.olderBusy).toBe(false);
    expect(pages.failed).toBeUndefined();
    expect(pages.nextEnd).toBe(5000);
  });
});

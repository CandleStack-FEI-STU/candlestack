import type { UseQueryResult } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';

import { ApiError, PAGE_SIZE, type Candles } from '@/api';
import { candles, times } from '@/test/candles';

import { restart, summarize } from './useCandleHistory';

// The parts of a query result that summarize reads.
function query(state: {
  data?: Candles;
  placeholder?: boolean;
  isFetching?: boolean;
  error?: Error;
}): UseQueryResult<Candles> {
  return {
    data: state.data,
    isPlaceholderData: state.placeholder ?? false,
    isFetching: state.isFetching ?? false,
    error: state.error ?? null,
    dataUpdatedAt: state.data ? 1 : 0,
  } as UseQueryResult<Candles>;
}

// Older pages hang below the anchor at 300; the latest page began there when they were asked.
const anchor = 300;
const before = candles([300, 360]);
const older = query({ data: candles([180, 240]) });
const noBridge = query({});
const timesOf = (bars: readonly { time: number }[]) => bars.map((bar) => bar.time);

describe('summarize', () => {
  const first = { latest: before, bridge: undefined };

  it('waits for an older page on its way and reports one that failed', () => {
    const loading = summarize({ latest: before, shown: first, anchor }, [noBridge, older, query({ isFetching: true })]);
    expect(loading.busy).toBe(true);
    expect(loading.nextEnd).toBeUndefined();
    const failed = query({ error: new Error('down') });
    expect(summarize({ latest: before, shown: first, anchor }, [noBridge, older, failed]).failed).toBe(failed);
  });

  it('keeps showing the latest page as it was until the first bridge arrives, so no hole shows', () => {
    // The latest page refreshed and now begins at 480; its first bridge is on its way.
    const latest = candles([480, 540]);
    const loading = summarize({ latest, shown: first, anchor }, [query({ isFetching: true }), older]);
    expect(timesOf(loading.history.bars)).toEqual([180, 240, 300, 360]);
    expect(loading.ready).toBe(false);
    // The next older page hangs below the anchor, which the bridge does not move.
    expect(loading.busy).toBe(false);
    expect(loading.nextEnd).toBe(180);
    const bridge = candles([300, 360, 420]);
    const arrived = summarize({ latest, shown: first, anchor }, [query({ data: bridge }), older]);
    expect(timesOf(arrived.history.bars)).toEqual([180, 240, 300, 360, 420, 480, 540]);
    expect(arrived.ready).toBe(true);
    expect(arrived.frame).toEqual({ latest, bridge });
  });

  it('keeps showing the last bridge with the latest page it led to while a longer one loads', () => {
    const shown = { latest: candles([420, 480]), bridge: candles([300, 360]) };
    const latest = candles([540, 600]);
    const last = query({ data: candles([300, 360]), placeholder: true, isFetching: true });
    const loading = summarize({ latest, shown, anchor }, [last, older]);
    expect(timesOf(loading.history.bars)).toEqual([180, 240, 300, 360, 420, 480]);
    expect(loading.ready).toBe(false);
  });

  it('keeps showing the last good bridge while the longer one fails, and lets it be retried', () => {
    // A 503, a 429 or no answer: the query has no data, but the chart keeps what it showed.
    const shown = { latest: candles([420, 480]), bridge: candles([300, 360]) };
    for (const error of [new ApiError(503, 'Down.'), new ApiError(429, 'Slow down.'), new ApiError(0, 'Offline.')]) {
      const bridge = query({ error });
      const pages = summarize({ latest: candles([540, 600]), shown, anchor }, [bridge, older]);
      expect(timesOf(pages.history.bars)).toEqual([180, 240, 300, 360, 420, 480]);
      expect(pages.tooFar).toBe(false);
      expect(pages.failed).toBe(bridge);
    }
  });

  it('starts history over, without an error, when the bridge is refused for good', () => {
    const refusals = [
      new ApiError(422, 'Use a shorter period.', { problem: 'too-many-candles' }),
      new ApiError(422, 'Set end after the start.', { problem: 'validation' }),
      new ApiError(404, 'No such instrument.', { problem: 'instrument-not-found' }),
    ];
    for (const error of refusals) {
      const pages = summarize({ latest: candles([600]), shown: first, anchor }, [query({ error }), older]);
      expect(pages.tooFar).toBe(true);
      expect(pages.failed).toBeUndefined();
    }
  });

  it('starts history over once a bridge answer holds two pages, missing candles counted', () => {
    const long = (count: number, gaps = 0) =>
      query({ data: candles(times(anchor, count), { gaps }), placeholder: true });
    const latest = candles([anchor + 60 * 2 * PAGE_SIZE]);
    const tooFar = (bridge: UseQueryResult<Candles>) =>
      summarize({ latest, shown: first, anchor }, [bridge, older]).tooFar;
    expect(tooFar(long(2 * PAGE_SIZE - 1))).toBe(false);
    expect(tooFar(long(2 * PAGE_SIZE))).toBe(true);
    expect(tooFar(long(2 * PAGE_SIZE - 10, 10))).toBe(true);
  });
});

describe('restart', () => {
  it('drops the older pages once for the anchor they hung from', () => {
    const chain = { olderEnds: [anchor, 180], restarts: 0 };
    const once = restart(chain, anchor);
    expect(once).toEqual({ olderEnds: [], restarts: 1 });
    // Another render with the same errored bridge: nothing changes.
    expect(restart(once, anchor)).toBe(once);
  });
});

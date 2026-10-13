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
  it('waits for an older page on its way and reports one that failed', () => {
    const loading = summarize({ latest: before, shown: before, anchor }, [
      noBridge,
      older,
      query({ isFetching: true }),
    ]);
    expect(loading.busy).toBe(true);
    expect(loading.olderBusy).toBe(true);
    expect(loading.nextEnd).toBeUndefined();
    const failed = query({ error: new Error('down') });
    expect(summarize({ latest: before, shown: before, anchor }, [noBridge, older, failed]).failed).toBe(failed);
  });

  it('keeps showing the latest page as it was until the first bridge arrives, so no hole shows', () => {
    // The latest page refreshed and now begins at 480; its first bridge is on its way.
    const latest = candles([480, 540]);
    const loading = summarize({ latest, shown: before, anchor }, [query({ isFetching: true }), older]);
    expect(timesOf(loading.history.bars)).toEqual([180, 240, 300, 360]);
    expect(loading.ready).toBe(false);
    expect(loading.busy).toBe(true);
    expect(loading.olderBusy).toBe(false);
    const arrived = summarize({ latest, shown: before, anchor }, [query({ data: candles([300, 360, 420]) }), older]);
    expect(timesOf(arrived.history.bars)).toEqual([180, 240, 300, 360, 420, 480, 540]);
    expect(arrived.ready).toBe(true);
  });

  it('keeps showing the last bridge with the latest page it led to while a longer one loads', () => {
    const shown = candles([420, 480]);
    const latest = candles([540, 600]);
    const last = query({ data: candles([300, 360]), placeholder: true, isFetching: true });
    const loading = summarize({ latest, shown, anchor }, [last, older]);
    expect(timesOf(loading.history.bars)).toEqual([180, 240, 300, 360, 420, 480]);
    expect(loading.ready).toBe(false);
  });

  it('starts history over when the gap is too big to bridge, without an error', () => {
    const tooMany = new ApiError(422, 'Use a shorter period.', { problem: 'too-many-candles' });
    const pages = summarize({ latest: candles([600]), shown: before, anchor }, [query({ error: tooMany }), older]);
    expect(pages.tooFar).toBe(true);
    expect(pages.failed).toBeUndefined();
    expect(pages.busy).toBe(false);
  });

  it('starts history over once the bridge reaches two pages instead of asking for ever more', () => {
    const long = (count: number) => query({ data: candles(times(anchor, count)), placeholder: true });
    const latest = candles([anchor + 60 * 2 * PAGE_SIZE]);
    expect(summarize({ latest, shown: before, anchor }, [long(2 * PAGE_SIZE - 1), older]).tooFar).toBe(false);
    expect(summarize({ latest, shown: before, anchor }, [long(2 * PAGE_SIZE), older]).tooFar).toBe(true);
  });

  it('reports a bridge that failed otherwise, so it can be retried', () => {
    const bridge = query({ error: new ApiError(503, 'Down.') });
    const pages = summarize({ latest: candles([600]), shown: before, anchor }, [bridge, older]);
    expect(pages.tooFar).toBe(false);
    expect(pages.failed).toBe(bridge);
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

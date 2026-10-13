import type { UseQueryResult } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';

import { ApiError, type Candles } from '@/api';
import { candles } from '@/test/candles';

import { restart, summarize } from './useCandleHistory';

// The parts of a query result that summarize reads.
function query(state: { data?: Candles; isFetching?: boolean; error?: Error }): UseQueryResult<Candles> {
  return {
    data: state.data,
    isFetching: state.isFetching ?? false,
    error: state.error ?? null,
    dataUpdatedAt: state.data ? 1 : 0,
  } as UseQueryResult<Candles>;
}

// Older pages hang below the anchor at 300; the latest page began there when they were asked.
const anchor = 300;
const before = candles([300, 360]);
const first = { latest: before, bridge: undefined };
const older = query({ data: candles([180, 240]) });
const noBridge = query({});
// The latest page refreshed and now begins at 480.
const latest = candles([480, 540]);
const timesOf = (bars: readonly { time: number }[]) => bars.map((bar) => bar.time);

describe('summarize', () => {
  it('waits for an older page on its way and reports one that failed', () => {
    const loading = summarize({ latest: before, shown: first, anchor }, [noBridge, older, query({ isFetching: true })]);
    expect(loading.busy).toBe(true);
    expect(loading.nextEnd).toBeUndefined();
    const failed = query({ error: new Error('down') });
    expect(summarize({ latest: before, shown: first, anchor }, [noBridge, older, failed]).failed).toBe(failed);
  });

  it('keeps showing the latest page as it was until the bridge arrives, so no hole shows', () => {
    const loading = summarize({ latest, shown: first, anchor }, [query({ isFetching: true }), older]);
    expect(timesOf(loading.history.bars)).toEqual([180, 240, 300, 360]);
    expect(loading.ready).toBe(false);
    // The next older page hangs below the anchor, which the bridge does not move.
    expect(loading.busy).toBe(false);
    expect(loading.nextEnd).toBe(180);
  });

  it('joins a bridge that reaches down to the anchor', () => {
    const bridge = candles([240, 300, 360, 420], { start: 240 });
    const arrived = summarize({ latest, shown: first, anchor }, [query({ data: bridge }), older]);
    expect(timesOf(arrived.history.bars)).toEqual([180, 240, 300, 360, 420, 480, 540]);
    expect(arrived.ready).toBe(true);
    expect(arrived.tooFar).toBe(false);
    expect(arrived.frame).toEqual({ latest, bridge });
  });

  it('starts history over when the bridge begins above the anchor: the gap is too big', () => {
    const short = candles([360, 420], { start: 360 });
    const pages = summarize({ latest, shown: first, anchor }, [query({ data: short }), older]);
    expect(pages.tooFar).toBe(true);
    expect(pages.ready).toBe(false);
    expect(timesOf(pages.history.bars)).toEqual([180, 240, 300, 360]);
  });

  it('keeps showing the last good frame while the bridge fails, and lets it be retried', () => {
    // A 503, a 429, no answer, or a refusal that may pass (403, 404, a 422 of another kind):
    // the chart keeps what it showed, and the error is shown to retry.
    const shown = { latest: candles([420, 480]), bridge: candles([300, 360]) };
    const errors = [
      new ApiError(503, 'Down.'),
      new ApiError(429, 'Slow down.'),
      new ApiError(0, 'Offline.'),
      new ApiError(403, 'Forbidden.'),
      new ApiError(404, 'No such instrument.', { problem: 'instrument-not-found' }),
      new ApiError(422, 'Bad request.', { problem: 'validation' }),
    ];
    for (const error of errors) {
      const bridge = query({ error });
      const pages = summarize({ latest: candles([540, 600]), shown, anchor }, [bridge, older]);
      expect(timesOf(pages.history.bars)).toEqual([180, 240, 300, 360, 420, 480]);
      expect(pages.tooFar).toBe(false);
      expect(pages.failed).toBe(bridge);
    }
  });

  it('starts history over, without an error, when the API cannot give the period', () => {
    const refusals = [
      new ApiError(422, 'Use a shorter period.', { problem: 'too-many-candles' }),
      new ApiError(422, 'Set end after the first candle.', { problem: 'period-out-of-range' }),
    ];
    for (const error of refusals) {
      const pages = summarize({ latest, shown: first, anchor }, [query({ error }), older]);
      expect(pages.tooFar).toBe(true);
      expect(pages.failed).toBeUndefined();
    }
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

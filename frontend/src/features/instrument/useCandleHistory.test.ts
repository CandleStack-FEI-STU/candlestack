import type { UseQueryResult } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';

import { ApiError, type Candles } from '@/api';
import { candles } from '@/test/candles';

import { summarize } from './useCandleHistory';

// The parts of a query result that summarize reads.
function query(state: { data?: Candles; isFetching?: boolean; error?: Error }): UseQueryResult<Candles> {
  return {
    data: state.data,
    isFetching: state.isFetching ?? false,
    error: state.error ?? null,
    dataUpdatedAt: state.data ? 1 : 0,
  } as UseQueryResult<Candles>;
}

const latest = candles([600, 660]);
const older = query({ data: candles([180, 240]) });
const noBridge = query({});

describe('summarize', () => {
  it('waits for an older page on its way and reports one that failed', () => {
    const loading = summarize(latest, [noBridge, older, query({ isFetching: true })], 300);
    expect(loading.busy).toBe(true);
    expect(loading.nextEnd).toBeUndefined();
    const failed = query({ error: new Error('down') });
    expect(summarize(latest, [noBridge, older, failed], 300).failed).toBe(failed);
  });

  it('joins the bridge to the history and waits while it loads', () => {
    const bridge = query({ data: candles([300, 360, 420, 480, 540]) });
    const pages = summarize(latest, [bridge, older], 300);
    expect(pages.history.bars.map((bar) => bar.time)).toEqual([180, 240, 300, 360, 420, 480, 540, 600, 660]);
    expect(pages.nextEnd).toBe(180);
    expect(summarize(latest, [query({ isFetching: true }), older], 300).busy).toBe(true);
  });

  it('starts history over when the gap is too big to bridge, without an error', () => {
    const tooMany = new ApiError(422, 'Use a shorter period.', { problem: 'too-many-candles' });
    const pages = summarize(latest, [query({ error: tooMany }), older], 300);
    expect(pages.tooFar).toBe(true);
    expect(pages.failed).toBeUndefined();
    expect(pages.busy).toBe(false);
  });

  it('reports a bridge that failed otherwise, so it can be retried', () => {
    const bridge = query({ error: new ApiError(503, 'Down.') });
    const pages = summarize(latest, [bridge, older], 300);
    expect(pages.tooFar).toBe(false);
    expect(pages.failed).toBe(bridge);
  });
});

import { queryOptions, skipToken } from '@tanstack/react-query';

import { get } from './client';
import type { components } from './schema';
import type { Timeframe } from './timeframes';

export type Candles = components['schemas']['CandlesOut'];

// How many candles one page shows: the chart opens with one page, scrolling left adds one more.
export const PAGE_SIZE = 500;

// What one request asks for: the last `limit` candles before `end` (now without it), or every
// candle from `start` to `end`. The API counts the candles by the market schedule itself.
export type CandleRange = { limit: number; end?: number } | { start: number; end: number };

// GET /api/v1/data/instruments/{id}/candles.
export function getCandles(
  instrument: string,
  timeframe: Timeframe,
  range: CandleRange,
  signal?: AbortSignal,
): Promise<Candles> {
  const query = new URLSearchParams({ timeframe });
  if ('start' in range) query.set('start', String(range.start));
  if (range.end !== undefined) query.set('end', String(range.end));
  if ('limit' in range) query.set('limit', String(range.limit));
  return get<Candles>(`/v1/data/instruments/${encodeURIComponent(instrument)}/candles?${query.toString()}`, signal);
}

export type CandlePage = {
  instrument: string;
  timeframe: Timeframe;
  // The instrument's `max_candles`: no page may ask for more.
  maxCandles: number;
  // History: the page ends here. Without it, the latest page, which ends now.
  end?: number;
};

// One page of candles: the last PAGE_SIZE before its end. Without `end` it is the latest page:
// it refreshes at most once a minute. With `end` it is history, which never changes: it stays
// cached for the whole visit, whatever the latest page does.
export function candlePageQueryOptions({ instrument, timeframe, maxCandles, end }: CandlePage) {
  return queryOptions({
    queryKey: ['candles', instrument, timeframe, end ?? 'latest'],
    queryFn: ({ signal }) => getCandles(instrument, timeframe, { limit: Math.min(PAGE_SIZE, maxCandles), end }, signal),
    staleTime: end === undefined ? 60_000 : Infinity,
    gcTime: end === undefined ? 5 * 60_000 : 30 * 60_000,
  });
}

export type CandleBridge = { instrument: string; timeframe: Timeframe; start?: number; end?: number };

// The candles between the older pages (which end at `start`) and the refreshed latest page
// (which begins at `end`): the ones that left the latest page as it moved on. They never change,
// but a refresh of the latest page asks for a longer bridge, so a bridge left behind goes soon.
// Without both ends there is no gap and nothing is asked. While a longer bridge from the same
// start loads, the shorter one before it stands in.
export function candleBridgeQueryOptions({ instrument, timeframe, start, end }: CandleBridge) {
  return queryOptions({
    queryKey: ['candles', instrument, timeframe, 'bridge', start ?? 'none', end ?? 'none'],
    queryFn:
      start === undefined || end === undefined
        ? skipToken
        : ({ signal }) => getCandles(instrument, timeframe, { start, end }, signal),
    meta: { start },
    placeholderData: (previous, previousQuery) =>
      end !== undefined && previousQuery?.meta?.['start'] === start ? previous : undefined,
    staleTime: Infinity,
    gcTime: 60_000,
  });
}

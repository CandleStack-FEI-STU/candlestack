import { queryOptions } from '@tanstack/react-query';

import { get } from './client';
import type { components } from './schema';
import type { Timeframe } from './timeframes';

export type Candles = components['schemas']['CandlesOut'];

// How many candles one page shows: the chart opens with one page, scrolling left adds one more.
export const PAGE_SIZE = 500;

export const TIMEFRAME_SECONDS: Record<Timeframe, number> = {
  '1m': 60,
  '5m': 300,
  '15m': 900,
  '30m': 1800,
  '1h': 3600,
  '4h': 14_400,
  '1d': 86_400,
};

// What one request asks for: the last `limit` candles before `end` (now without it), or every
// candle from `start` up to now. The API counts the candles by the market schedule itself.
export type CandleRange = { limit: number; end?: number } | { start: number };

// GET /api/v1/data/instruments/{id}/candles.
export function getCandles(
  instrument: string,
  timeframe: Timeframe,
  range: CandleRange,
  signal?: AbortSignal,
): Promise<Candles> {
  const query = new URLSearchParams({ timeframe });
  if ('start' in range) {
    query.set('start', String(range.start));
  } else {
    if (range.end !== undefined) query.set('end', String(range.end));
    query.set('limit', String(range.limit));
  }
  return get<Candles>(`/v1/data/instruments/${encodeURIComponent(instrument)}/candles?${query.toString()}`, signal);
}

export type CandlePage = {
  instrument: string;
  timeframe: Timeframe;
  // The instrument's `max_candles`: no request may ask for more.
  maxCandles: number;
  // History: the page ends here. Without it, the latest page, which ends now.
  end?: number;
  // Latest page only: reach down at least to here, where the older pages begin.
  since?: number;
};

// What a page asks for at `now`. A page of history is the last candles before its end. The
// latest page, once older pages hang below it, asks for everything from `since`, so a refresh
// after a long idle time cannot open a hole between it and the history. Every timeframe up to
// now counts as a candle there (stocks have fewer), so that request stays within `maxCandles`;
// when it would not, the latest page asks for its last candles again and the history below it is
// dropped (`mergePages`).
export function pageRange({ timeframe, maxCandles, end, since }: CandlePage, now: number): CandleRange {
  const limit = Math.min(PAGE_SIZE, maxCandles);
  if (end !== undefined) return { limit, end };
  if (since !== undefined && Math.ceil((now - since) / TIMEFRAME_SECONDS[timeframe]) + 1 <= maxCandles) {
    return { start: since };
  }
  return { limit };
}

// One page of candles. Without `end` it is the latest page: it refreshes at most once a minute.
// With `end` it is history, which never changes: it stays cached for the whole visit.
// `since` is left out of the key on purpose: when it is first set it is the start of the cached
// latest page, so that page is already right; it only changes what later refreshes ask for.
export function candlePageQueryOptions(page: CandlePage) {
  const { instrument, timeframe, end } = page;
  return queryOptions({
    queryKey: ['candles', instrument, timeframe, end ?? 'latest'],
    queryFn: ({ signal }) => getCandles(instrument, timeframe, pageRange(page, Math.floor(Date.now() / 1000)), signal),
    staleTime: end === undefined ? 60_000 : Infinity,
    gcTime: end === undefined ? 5 * 60_000 : 30 * 60_000,
  });
}

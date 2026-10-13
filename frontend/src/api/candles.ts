import { queryOptions } from '@tanstack/react-query';

import { ApiError, get } from './client';
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

// The most candles the latest page asks for from `since`: a page or two of new candles is what
// a minute or a short idle time adds. Longer, it would download days of candles every minute;
// it asks for its last candles again instead and the history below it starts over.
const SINCE_CANDLES = 2 * PAGE_SIZE;

// The latest page as the API last sent it, and when it came (epoch seconds, browser clock).
export type LastAnswer = { candles: Candles; at: number };

// What a page asks for at `now`. A page of history is the last candles before its end. The
// latest page, once older pages hang below it, asks for everything from `since`, so a refresh
// cannot open a hole between it and the history. How many candles that is comes from the last
// answer, which reached down to `since`, plus every timeframe since it came (an upper bound for
// that short time: stocks have fewer). A tenth of `maxCandles` is left for a browser clock that
// runs behind the server's.
export function pageRange(
  { timeframe, maxCandles, end, since }: CandlePage,
  now: number,
  last?: LastAnswer,
): CandleRange {
  const limit = Math.min(PAGE_SIZE, maxCandles);
  if (end !== undefined) return { limit, end };
  if (since === undefined || last === undefined || last.candles.meta.start > since) return { limit };
  const held = last.candles.t.length + last.candles.meta.gaps_total;
  const estimate = held + Math.ceil((now - last.at) / TIMEFRAME_SECONDS[timeframe]) + 1;
  return estimate <= Math.min(SINCE_CANDLES, Math.floor(maxCandles * 0.9)) ? { start: since } : { limit };
}

// One page of candles. Without `end` it is the latest page: it refreshes at most once a minute.
// With `end` it is history, which never changes: it stays cached for the whole visit.
// `since` is left out of the key on purpose: when it is first set it is the start of the cached
// latest page, so that page is already right; it only changes what later refreshes ask for.
export function candlePageQueryOptions(page: CandlePage) {
  const { instrument, timeframe, end } = page;
  return queryOptions({
    queryKey: ['candles', instrument, timeframe, end ?? 'latest'],
    queryFn: async ({ client, queryKey, signal }) => {
      const now = Math.floor(Date.now() / 1000);
      const state = client.getQueryState<Candles>(queryKey);
      const last = state?.data && { candles: state.data, at: Math.floor(state.dataUpdatedAt / 1000) };
      const range = pageRange(page, now, last);
      try {
        return await getCandles(instrument, timeframe, range, signal);
      } catch (error) {
        // The server counts up to its own clock, which may be ahead of the browser's: then the
        // latest page asks for its last candles, as after a long idle time.
        if ('start' in range && error instanceof ApiError && error.problem === 'too-many-candles') {
          return getCandles(instrument, timeframe, pageRange({ ...page, since: undefined }, now), signal);
        }
        throw error;
      }
    },
    staleTime: end === undefined ? 60_000 : Infinity,
    gcTime: end === undefined ? 5 * 60_000 : 30 * 60_000,
  });
}

import { queryOptions } from '@tanstack/react-query';

import { get } from './client';
import type { components } from './schema';
import type { Timeframe } from './timeframes';

export type Candles = components['schemas']['CandlesOut'];

// How many candles the API returns on one chart page.
export const PAGE_SIZE = 500;

// GET /api/v1/data/instruments/{id}/candles.
export function getCandles(
  instrument: string,
  timeframe: Timeframe,
  end?: number,
  signal?: AbortSignal,
): Promise<Candles> {
  const query = new URLSearchParams({ timeframe });
  if (end !== undefined) query.set('end', String(end));
  query.set('limit', String(PAGE_SIZE));
  return get<Candles>(`/v1/data/instruments/${encodeURIComponent(instrument)}/candles?${query.toString()}`, signal);
}

export type CandlePage = {
  instrument: string;
  timeframe: Timeframe;
  // History: the page ends here. Without it, the latest page, which ends now.
  end?: number;
};

// One page of candles. Without `end` it is the latest page: it refreshes at most once a minute.
// With `end` it is history, which never changes: it stays cached for the whole visit.
export function candlePageQueryOptions({ instrument, timeframe, end }: CandlePage) {
  return queryOptions({
    queryKey: ['candles', instrument, timeframe, end ?? 'latest'],
    queryFn: ({ signal }) => getCandles(instrument, timeframe, end, signal),
    staleTime: end === undefined ? 60_000 : Infinity,
    gcTime: end === undefined ? 5 * 60_000 : 30 * 60_000,
  });
}

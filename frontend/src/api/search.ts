import { keepPreviousData, queryOptions } from '@tanstack/react-query';

import { get } from './client';
import type { Market } from './instruments';
import type { components } from './schema';

export type Instrument = components['schemas']['InstrumentOut'];
export type InstrumentSearchResult = components['schemas']['InstrumentSearchOut'];

export type InstrumentSearchParams = { q: string; market?: Market; limit: number; offset: number };

// GET /api/v1/data/instruments. Search is not rate-limited, and it reads cached catalogs only.
export function searchInstruments(params: InstrumentSearchParams, signal?: AbortSignal) {
  const query = new URLSearchParams({ limit: String(params.limit), offset: String(params.offset) });
  if (params.q !== '') query.set('q', params.q);
  if (params.market) query.set('market', params.market);
  return get<InstrumentSearchResult>(`/v1/data/instruments?${query.toString()}`, signal);
}

// While the next page or query loads, the previous result stays on screen instead of a blank
// table. A minute of freshness: the catalogs change once a day.
export function instrumentSearchQueryOptions(params: InstrumentSearchParams) {
  return queryOptions({
    queryKey: ['instruments', params],
    queryFn: ({ signal }) => searchInstruments(params, signal),
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  });
}

// Is there a page after this one? The API before #109 (still on prod until the next release)
// sends no `total`; then a full page means there may be more.
export function hasNextPage(result: InstrumentSearchResult, limit: number): boolean {
  const total = (result as Partial<InstrumentSearchResult>).total;
  const offset = (result as Partial<InstrumentSearchResult>).offset ?? 0;
  if (total === undefined) return result.count >= limit;
  return offset + result.count < total;
}

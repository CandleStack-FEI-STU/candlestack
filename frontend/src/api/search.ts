import { keepPreviousData, queryOptions } from '@tanstack/react-query';

import { get } from './client';
import type { Market } from './instruments';
import type { components } from './schema';

export type Instrument = components['schemas']['InstrumentOut'];
export type InstrumentSearchResult = components['schemas']['InstrumentSearchOut'];

export type Exchange = components['schemas']['Exchange'];

// The exchanges the API filters by, in the order the filter shows them. `satisfies` keeps the
// list in step with the generated type: a value the API drops fails the type check.
export const EXCHANGES = ['NASDAQ', 'NYSE', 'ARCA', 'AMEX', 'BATS'] as const satisfies readonly Exchange[];

export type InstrumentSearchParams = {
  q: string;
  market?: Market;
  // Only stocks listed there; crypto pairs have no exchange.
  exchange?: Exchange;
  limit: number;
  offset: number;
};

// GET /api/v1/data/instruments. Search is not rate-limited, and it reads cached catalogs only.
export function searchInstruments(params: InstrumentSearchParams, signal?: AbortSignal) {
  const query = new URLSearchParams({ limit: String(params.limit), offset: String(params.offset) });
  if (params.q !== '') query.set('q', params.q);
  if (params.market) query.set('market', params.market);
  if (params.exchange) query.set('exchange', params.exchange);
  return get<InstrumentSearchResult>(`/v1/data/instruments?${query.toString()}`, signal);
}

// While the next page or query loads, the previous result stays on screen instead of a blank
// table. Fresh for the client's default minute: the catalogs change once a day.
export function instrumentSearchQueryOptions(params: InstrumentSearchParams) {
  return queryOptions({
    queryKey: ['instruments', params],
    queryFn: ({ signal }) => searchInstruments(params, signal),
    placeholderData: keepPreviousData,
  });
}

// How many instruments match in all, or undefined from the API before #109 (still on prod until
// the next release), which sends no `total` and no `offset`. The type says both are always
// there; this is the one place that knows better.
export function resultTotal(result: InstrumentSearchResult): number | undefined {
  return (result as Partial<InstrumentSearchResult>).total;
}

// Is there a page after this one? Without a total, a full page means there may be more.
export function hasNextPage(result: InstrumentSearchResult, limit: number): boolean {
  const total = resultTotal(result);
  if (total === undefined) return result.count >= limit;
  return (result.offset ?? 0) + result.count < total;
}

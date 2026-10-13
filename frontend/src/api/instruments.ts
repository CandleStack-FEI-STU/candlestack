import { queryOptions } from '@tanstack/react-query';

import { apiUrl, get } from './client';
import type { components } from './schema';

export type InstrumentDetail = components['schemas']['InstrumentDetailOut'];
export type Market = components['schemas']['Market'];

// The exchange to show for an instrument. The API gives stocks their listing exchange and crypto
// pairs none (null): they all come from Binance, which is the exchange. Shared by the list and
// the instrument page, so both say the same.
export function exchangeName(instrument: Pick<InstrumentDetail, 'exchange' | 'source'>): string {
  return instrument.exchange ?? (instrument.source === 'binance' ? 'Binance' : '—');
}

// The path of an instrument; an id has a colon, e.g. "stock:BRK.B".
function instrumentPath(id: string): string {
  return `/v1/data/instruments/${encodeURIComponent(id)}`;
}

// GET /api/v1/data/instruments/{id}. Counts against the 60 per minute limit like the candles.
export function getInstrument(id: string, signal?: AbortSignal): Promise<InstrumentDetail> {
  return get<InstrumentDetail>(instrumentPath(id), signal);
}

// GET /api/v1/data/instruments/{id}/icon, the src of an <img>: always an image (the logo or the
// fallback), never an error for an instrument of the catalog. Not counted against the limit.
export function instrumentIconUrl(id: string): string {
  return apiUrl(`${instrumentPath(id)}/icon`);
}

// One cache entry per instrument, shared by the route loader and the page. The catalog
// changes rarely: ten minutes of freshness spares the rate limit on every visit.
export function instrumentQueryOptions(id: string) {
  return queryOptions({
    queryKey: ['instrument', id],
    queryFn: ({ signal }) => getInstrument(id, signal),
    staleTime: 10 * 60_000,
  });
}

import type { SearchSchemaInput } from '@tanstack/react-router';

import type { Market } from '@/api';

// The list page keeps the query, the market and the page in the URL, so a search can be shared
// and Back returns to it: /?q=btc&market=crypto&page=2.
export type InstrumentsSearch = { q?: string; market?: Market; page?: number };

const MAX_QUERY = 50; // the API's limit for `q`

function parseQuery(value: unknown): string | undefined {
  if (typeof value !== 'string' && typeof value !== 'number') return undefined;
  const q = String(value).trim().slice(0, MAX_QUERY);
  return q === '' ? undefined : q;
}

function parseMarket(value: unknown): Market | undefined {
  return value === 'stock' || value === 'crypto' ? value : undefined;
}

function parsePage(value: unknown): number | undefined {
  const page = Number(value);
  return Number.isInteger(page) && page > 1 ? page : undefined;
}

// Unknown or broken values are dropped, so ?market=bonds or ?page=-3 opens the plain list.
// Defaults are left out of the URL: the page reads a missing value as "all" or page 1.
export function validateInstrumentsSearch(
  search: { q?: unknown; market?: unknown; page?: unknown } & SearchSchemaInput,
): InstrumentsSearch {
  const result: InstrumentsSearch = {};
  const q = parseQuery(search.q);
  const market = parseMarket(search.market);
  const page = parsePage(search.page);
  if (q !== undefined) result.q = q;
  if (market !== undefined) result.market = market;
  if (page !== undefined) result.page = page;
  return result;
}

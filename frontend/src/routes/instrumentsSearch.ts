import type { SearchSchemaInput } from '@tanstack/react-router';

import { EXCHANGES, type Exchange, type Market } from '@/api';

// The orders of the list other than the default, the 24 h volume (#184).
export type ListSort = 'gainers' | 'losers' | 'symbol';

// The list page keeps the query, the market, the exchange, the order and the page in the URL, so
// a search can be shared and Back returns to it: /?q=apple&market=stock&exchange=NASDAQ&sort=gainers&page=2.
export type InstrumentsSearch = { q?: string; market?: Market; exchange?: Exchange; sort?: ListSort; page?: number };

const SORTS: readonly ListSort[] = ['gainers', 'losers', 'symbol'];

const MAX_QUERY = 50; // the API's limit for `q`

function parseQuery(value: unknown): string | undefined {
  if (typeof value !== 'string' && typeof value !== 'number') return undefined;
  const q = String(value).trim().slice(0, MAX_QUERY);
  return q === '' ? undefined : q;
}

function parseMarket(value: unknown): Market | undefined {
  return value === 'stock' || value === 'crypto' ? value : undefined;
}

// Kept even when the market does not trade there (?market=crypto&exchange=NYSE, an old or
// hand-edited link): the list then says why it is empty instead of quietly dropping a filter.
function parseExchange(value: unknown): Exchange | undefined {
  return EXCHANGES.find((exchange) => exchange === value);
}

function parseSort(value: unknown): ListSort | undefined {
  return SORTS.find((sort) => sort === value);
}

// A safe integer only: ?page=1e20 would send offset=5e+21, which the API rejects.
function parsePage(value: unknown): number | undefined {
  const page = Number(value);
  return Number.isSafeInteger(page) && page > 1 ? page : undefined;
}

// Unknown or broken values are dropped, so ?market=bonds or ?page=-3 opens the plain list.
// Defaults are left out of the URL: the page reads a missing value as "all" or page 1.
export function validateInstrumentsSearch(
  search: { q?: unknown; market?: unknown; exchange?: unknown; sort?: unknown; page?: unknown } & SearchSchemaInput,
): InstrumentsSearch {
  const result: InstrumentsSearch = {};
  const q = parseQuery(search.q);
  const market = parseMarket(search.market);
  const exchange = parseExchange(search.exchange);
  const sort = parseSort(search.sort);
  const page = parsePage(search.page);
  if (q !== undefined) result.q = q;
  if (market !== undefined) result.market = market;
  if (exchange !== undefined) result.exchange = exchange;
  if (sort !== undefined) result.sort = sort;
  if (page !== undefined) result.page = page;
  return result;
}

import { afterEach, describe, expect, it, vi } from 'vitest';

import { hasNextPage, instrumentSearchQueryOptions, searchInstruments, type InstrumentSearchResult } from './search';

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubFetch() {
  const fetch = vi.fn(() => Promise.resolve(new Response('{"items":[]}')));
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

describe('searchInstruments', () => {
  it('sends the query, market and page', async () => {
    const fetch = stubFetch();
    await searchInstruments({ q: 'btc/usdt', market: 'crypto', limit: 50, offset: 100 });
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/data/instruments?limit=50&offset=100&q=btc%2Fusdt&market=crypto',
      expect.anything(),
    );
  });

  it('sends the exchange', async () => {
    const fetch = stubFetch();
    await searchInstruments({ q: '', exchange: 'NYSE', limit: 50, offset: 0 });
    expect(fetch).toHaveBeenCalledWith('/api/v1/data/instruments?limit=50&offset=0&exchange=NYSE', expect.anything());
  });

  it('leaves out an empty query and "all markets", so the API lists everything', async () => {
    const fetch = stubFetch();
    await searchInstruments({ q: '', limit: 50, offset: 0 });
    expect(fetch).toHaveBeenCalledWith('/api/v1/data/instruments?limit=50&offset=0', expect.anything());
  });
});

describe('instrumentSearchQueryOptions', () => {
  it('caches each query, market and page apart', () => {
    const a = instrumentSearchQueryOptions({ q: 'btc', limit: 50, offset: 0 });
    const b = instrumentSearchQueryOptions({ q: 'btc', limit: 50, offset: 50 });
    expect(a.queryKey).not.toEqual(b.queryKey);
  });
});

function result(count: number, total?: number, offset?: number): InstrumentSearchResult {
  return { items: [], count, total, offset, unavailable: [] } as unknown as InstrumentSearchResult;
}

describe('hasNextPage', () => {
  it('pages while offset + count is below total', () => {
    expect(hasNextPage(result(50, 120, 0), 50)).toBe(true);
    expect(hasNextPage(result(50, 120, 50), 50)).toBe(true);
    expect(hasNextPage(result(20, 120, 100), 50)).toBe(false);
    expect(hasNextPage(result(50, 100, 50), 50)).toBe(false);
  });

  it('without total (the API before #109) takes a full page as "maybe more"', () => {
    expect(hasNextPage(result(50), 50)).toBe(true);
    expect(hasNextPage(result(12), 50)).toBe(false);
  });
});

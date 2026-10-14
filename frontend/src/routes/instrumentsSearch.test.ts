import { describe, expect, it } from 'vitest';

import { validateInstrumentsSearch } from './instrumentsSearch';

type RawSearch = Parameters<typeof validateInstrumentsSearch>[0];
const validate = (search: Record<string, unknown>) => validateInstrumentsSearch(search as RawSearch);

describe('validateInstrumentsSearch', () => {
  it('keeps a query, a market and a page', () => {
    expect(validate({ q: ' btc ', market: 'crypto', page: '3' })).toEqual({ q: 'btc', market: 'crypto', page: 3 });
  });

  it('keeps a known exchange, Binance too', () => {
    expect(validate({ market: 'stock', exchange: 'NYSE' })).toEqual({ market: 'stock', exchange: 'NYSE' });
    expect(validate({ exchange: 'NASDAQ' })).toEqual({ exchange: 'NASDAQ' });
    expect(validate({ exchange: 'BINANCE' })).toEqual({ exchange: 'BINANCE' });
    expect(validate({ market: 'crypto', exchange: 'BINANCE', page: 2 })).toEqual({
      market: 'crypto',
      exchange: 'BINANCE',
      page: 2,
    });
    expect(validate({ exchange: 'LSE' })).toEqual({});
    expect(validate({ exchange: 'nyse' })).toEqual({});
    expect(validate({ exchange: 'Binance' })).toEqual({});
  });

  it('keeps an exchange the market does not trade on, so the list can say why it is empty', () => {
    expect(validate({ market: 'crypto', exchange: 'NYSE' })).toEqual({ market: 'crypto', exchange: 'NYSE' });
    expect(validate({ market: 'stock', exchange: 'BINANCE' })).toEqual({ market: 'stock', exchange: 'BINANCE' });
  });

  it('keeps an order other than the default, the 24 h volume', () => {
    expect(validate({ sort: 'gainers' })).toEqual({ sort: 'gainers' });
    expect(validate({ sort: 'losers', market: 'stock', page: 2 })).toEqual({
      sort: 'losers',
      market: 'stock',
      page: 2,
    });
    expect(validate({ sort: 'symbol' })).toEqual({ sort: 'symbol' });
    // the default and the API's own names are not the URL's
    expect(validate({ sort: 'volume' })).toEqual({});
    expect(validate({ sort: '-change' })).toEqual({});
    expect(validate({ sort: ['gainers'] })).toEqual({});
  });

  it('reads a number as a query (?q=500 arrives as a number)', () => {
    expect(validate({ q: 500 })).toEqual({ q: '500' });
  });

  it('drops defaults and broken values', () => {
    expect(validate({})).toEqual({});
    expect(validate({ q: '   ', market: 'bonds', page: 1 })).toEqual({});
    expect(validate({ page: -3 })).toEqual({});
    expect(validate({ page: 2.5 })).toEqual({});
    // offset=5e+21 would be a 422 from the API
    expect(validate({ page: '1e20' })).toEqual({});
    expect(validate({ q: ['btc'] })).toEqual({});
  });

  it('cuts a query to the API limit of 50 characters', () => {
    expect(validate({ q: 'x'.repeat(80) }).q).toHaveLength(50);
  });
});

import { describe, expect, it } from 'vitest';

import { validateInstrumentsSearch } from './instrumentsSearch';

type RawSearch = Parameters<typeof validateInstrumentsSearch>[0];
const validate = (search: Record<string, unknown>) => validateInstrumentsSearch(search as RawSearch);

describe('validateInstrumentsSearch', () => {
  it('keeps a query, a market and a page', () => {
    expect(validate({ q: ' btc ', market: 'crypto', page: '3' })).toEqual({ q: 'btc', market: 'crypto', page: 3 });
  });

  it('reads a number as a query (?q=500 arrives as a number)', () => {
    expect(validate({ q: 500 })).toEqual({ q: '500' });
  });

  it('drops defaults and broken values', () => {
    expect(validate({})).toEqual({});
    expect(validate({ q: '   ', market: 'bonds', page: 1 })).toEqual({});
    expect(validate({ page: -3 })).toEqual({});
    expect(validate({ page: 2.5 })).toEqual({});
    expect(validate({ q: ['btc'] })).toEqual({});
  });

  it('cuts a query to the API limit of 50 characters', () => {
    expect(validate({ q: 'x'.repeat(80) }).q).toHaveLength(50);
  });
});

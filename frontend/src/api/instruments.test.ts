import { afterEach, describe, expect, it, vi } from 'vitest';

import { exchangeName, getInstrument, instrumentIconUrl, instrumentQueryOptions } from './instruments';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('getInstrument', () => {
  it('asks for the instrument by its id', async () => {
    const fetch = vi.fn(() => Promise.resolve(new Response('{"id":"stock:BRK.B"}')));
    vi.stubGlobal('fetch', fetch);
    await expect(getInstrument('stock:BRK.B')).resolves.toEqual({ id: 'stock:BRK.B' });
    expect(fetch).toHaveBeenCalledWith('/api/v1/data/instruments/stock%3ABRK.B', expect.anything());
  });

  it('shares one cache entry per instrument between the loader and the page', () => {
    expect(instrumentQueryOptions('crypto:BTCUSDT').queryKey).toEqual(['instrument', 'crypto:BTCUSDT']);
  });
});

describe('instrumentIconUrl', () => {
  it('points at the icon of the instrument by its id', () => {
    expect(instrumentIconUrl('stock:BRK.B')).toBe('/api/v1/data/instruments/stock%3ABRK.B/icon');
  });
});

describe('exchangeName', () => {
  it('names the listing exchange of a stock and Binance for a crypto pair', () => {
    expect(exchangeName({ exchange: 'NASDAQ', market: 'stock' })).toBe('NASDAQ');
    expect(exchangeName({ exchange: 'BINANCE', market: 'crypto' })).toBe('Binance');
    // the API before #182
    expect(exchangeName({ exchange: null, market: 'crypto' })).toBe('Binance');
    // a stock on an exchange outside the filter's list
    expect(exchangeName({ exchange: null, market: 'stock' })).toBe('—');
  });
});

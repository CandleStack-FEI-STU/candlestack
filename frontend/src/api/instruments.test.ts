import { afterEach, describe, expect, it, vi } from 'vitest';

import { exchangeName, getInstrument, instrumentQueryOptions } from './instruments';

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

describe('exchangeName', () => {
  it('names the listing exchange of a stock and Binance for a crypto pair', () => {
    expect(exchangeName({ exchange: 'NASDAQ', source: 'alpaca' })).toBe('NASDAQ');
    expect(exchangeName({ exchange: null, source: 'binance' })).toBe('Binance');
    expect(exchangeName({ exchange: null, source: 'alpaca' })).toBe('—');
  });
});

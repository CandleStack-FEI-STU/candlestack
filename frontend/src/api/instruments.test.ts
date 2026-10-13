import { afterEach, describe, expect, it, vi } from 'vitest';

import { exchangeLabel, exchangeName, getInstrument, instrumentIconUrl, instrumentQueryOptions } from './instruments';

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

describe('exchangeLabel', () => {
  it('names Binance as the company writes it and a stock exchange by its code', () => {
    expect(exchangeLabel('BINANCE')).toBe('Binance');
    expect(exchangeLabel('NYSE')).toBe('NYSE');
  });
});

describe('exchangeName', () => {
  it('names the listing exchange of a stock and Binance for a crypto pair', () => {
    expect(exchangeName({ exchange: 'NASDAQ', source: 'alpaca' })).toBe('NASDAQ');
    expect(exchangeName({ exchange: 'BINANCE', source: 'binance' })).toBe('Binance');
    // the API before #182
    expect(exchangeName({ exchange: null, source: 'binance' })).toBe('Binance');
    expect(exchangeName({ exchange: null, source: 'alpaca' })).toBe('—');
  });
});

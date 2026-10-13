import { afterEach, describe, expect, it, vi } from 'vitest';

import { PAGE_SIZE, candlePageQueryOptions, getCandles } from './candles';

const END = 1_780_000_000;

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('getCandles', () => {
  it('asks for the latest page by limit without guessing a start time', async () => {
    const fetch = vi.fn(() => Promise.resolve(new Response('{"t":[]}')));
    vi.stubGlobal('fetch', fetch);
    await getCandles('crypto:BTCUSDT', '1h');
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/data/instruments/crypto%3ABTCUSDT/candles?timeframe=1h&limit=500',
      expect.anything(),
    );
  });

  it('asks for an older page before its first candle, with the same limit', async () => {
    const fetch = vi.fn(() => Promise.resolve(new Response('{"t":[]}')));
    vi.stubGlobal('fetch', fetch);
    await getCandles('stock:AAPL', '1h', END);
    expect(fetch).toHaveBeenCalledWith(
      `/api/v1/data/instruments/stock%3AAAPL/candles?timeframe=1h&end=${END}&limit=${PAGE_SIZE}`,
      expect.anything(),
    );
  });
});

describe('candlePageQueryOptions', () => {
  const base = { instrument: 'crypto:BTCUSDT', timeframe: '1h' } as const;

  it('keys the latest page apart and lets it refresh after a minute', () => {
    const latest = candlePageQueryOptions(base);
    expect(latest.queryKey).toEqual(['candles', 'crypto:BTCUSDT', '1h', 'latest']);
    expect(latest.staleTime).toBe(60_000);
  });

  it('keys an older page by its end and keeps it for good', () => {
    const older = candlePageQueryOptions({ ...base, end: END });
    expect(older.queryKey).toEqual(['candles', 'crypto:BTCUSDT', '1h', END]);
    expect(older.staleTime).toBe(Infinity);
  });
});

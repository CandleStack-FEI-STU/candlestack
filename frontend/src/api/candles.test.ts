import { afterEach, describe, expect, it, vi } from 'vitest';

import { PAGE_SIZE, candlePageQueryOptions, getCandles, pageRange } from './candles';

const END = 1_780_000_000;

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('getCandles', () => {
  it('asks the candles endpoint of the instrument for the last candles before an end', async () => {
    const fetch = vi.fn(() => Promise.resolve(new Response('{"t":[]}')));
    vi.stubGlobal('fetch', fetch);
    await getCandles('crypto:BTCUSDT', '1h', { limit: 500, end: END });
    expect(fetch).toHaveBeenCalledWith(
      `/api/v1/data/instruments/crypto%3ABTCUSDT/candles?timeframe=1h&end=${END}&limit=500`,
      expect.anything(),
    );
  });

  it('leaves out the end of the latest candles and the end of a period up to now', async () => {
    const fetch = vi.fn(() => Promise.resolve(new Response('{"t":[]}')));
    vi.stubGlobal('fetch', fetch);
    await getCandles('stock:AAPL', '1h', { limit: 500 });
    await getCandles('stock:AAPL', '1h', { start: END });
    expect(fetch).toHaveBeenNthCalledWith(
      1,
      '/api/v1/data/instruments/stock%3AAAPL/candles?timeframe=1h&limit=500',
      expect.anything(),
    );
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      `/api/v1/data/instruments/stock%3AAAPL/candles?timeframe=1h&start=${END}`,
      expect.anything(),
    );
  });
});

describe('pageRange', () => {
  const base = { instrument: 'crypto:BTCUSDT', timeframe: '1h', maxCandles: 50_000 } as const;

  it('asks for the last PAGE_SIZE candles, before the end of an older page', () => {
    expect(pageRange(base, END)).toEqual({ limit: PAGE_SIZE });
    expect(pageRange({ ...base, end: END - 3600 }, END)).toEqual({ limit: PAGE_SIZE, end: END - 3600 });
  });

  it('never asks for more candles than the server allows', () => {
    expect(pageRange({ ...base, maxCandles: 200 }, END)).toEqual({ limit: 200 });
    expect(pageRange({ ...base, maxCandles: 200, end: END - 3600 }, END)).toEqual({ limit: 200, end: END - 3600 });
  });

  it('reaches the latest page down to the history below it, however long the tab sat idle', () => {
    const since = END - 3 * PAGE_SIZE * 3600;
    expect(pageRange({ ...base, since }, END)).toEqual({ start: since });
  });

  it('asks for the last candles again when the stretch down to the history is over the maximum', () => {
    const maxCandles = 1000;
    expect(pageRange({ ...base, maxCandles, since: END - 999 * 3600 }, END)).toEqual({ start: END - 999 * 3600 });
    expect(pageRange({ ...base, maxCandles, since: END - 1000 * 3600 }, END)).toEqual({ limit: PAGE_SIZE });
  });
});

describe('candlePageQueryOptions', () => {
  const base = { instrument: 'crypto:BTCUSDT', timeframe: '1h', maxCandles: 50_000 } as const;

  it('keys the latest page apart and lets it refresh after a minute', () => {
    const latest = candlePageQueryOptions(base);
    expect(latest.queryKey).toEqual(['candles', 'crypto:BTCUSDT', '1h', 'latest']);
    expect(latest.staleTime).toBe(60_000);
  });

  it('keeps an older page for good: history does not change', () => {
    const older = candlePageQueryOptions({ ...base, end: END });
    expect(older.queryKey).toEqual(['candles', 'crypto:BTCUSDT', '1h', END]);
    expect(older.staleTime).toBe(Infinity);
  });

  it('keeps the key of the latest page with history below it, so the first older page costs no extra request', () => {
    expect(candlePageQueryOptions({ ...base, since: END }).queryKey).toEqual(candlePageQueryOptions(base).queryKey);
  });

  it('refreshes the latest page from `since` with history below it', async () => {
    const fetch = vi.fn(() => Promise.resolve(new Response('{"t":[]}')));
    vi.stubGlobal('fetch', fetch);
    const since = Math.floor(Date.now() / 1000) - 3 * PAGE_SIZE * 3600;
    const { queryFn } = candlePageQueryOptions({ ...base, since });
    await (queryFn as (context: { signal: AbortSignal }) => Promise<unknown>)({ signal: new AbortController().signal });
    expect(fetch).toHaveBeenCalledWith(
      `/api/v1/data/instruments/crypto%3ABTCUSDT/candles?timeframe=1h&start=${since}`,
      expect.anything(),
    );
  });
});

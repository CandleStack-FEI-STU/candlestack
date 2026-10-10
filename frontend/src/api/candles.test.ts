import { afterEach, describe, expect, it, vi } from 'vitest';

import { PAGE_SIZE, candlePageQueryOptions, candleWindow, getCandles, latestWindow } from './candles';

const END = 1_780_000_000;

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('candleWindow', () => {
  it('spans exactly one page of candles for crypto, which trades around the clock', () => {
    expect(candleWindow('crypto', '1h', END)).toEqual({ start: END - PAGE_SIZE * 3600, end: END });
    expect(candleWindow('crypto', '1m', END)).toEqual({ start: END - PAGE_SIZE * 60, end: END });
  });

  it('widens the window for stocks by the share of time the market is closed', () => {
    const { start } = candleWindow('stock', '1h', END);
    const days = (END - start) / 86_400;
    // 500 hourly candles at 6.5 hours a day on 252 days a year: about 110 calendar days.
    expect(days).toBeGreaterThan(100);
    expect(days).toBeLessThan(120);
    const daily = (END - candleWindow('stock', '1d', END).start) / 86_400;
    expect(daily).toBeCloseTo((PAGE_SIZE * 365) / 252, 0);
  });

  it('never makes a stock window shorter than a long weekend', () => {
    const { start } = candleWindow('stock', '1m', END);
    expect(END - start).toBeGreaterThanOrEqual(PAGE_SIZE * 60 + 4 * 86_400);
  });
});

describe('getCandles', () => {
  it('asks the candles endpoint for the window', async () => {
    const fetch = vi.fn(() => Promise.resolve(new Response('{"t":[]}')));
    vi.stubGlobal('fetch', fetch);
    await getCandles('crypto:BTCUSDT', '1h', { start: 1, end: 2 });
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/data/candles?instrument=crypto%3ABTCUSDT&timeframe=1h&start=1&end=2',
      expect.anything(),
    );
  });
});

describe('candlePageQueryOptions', () => {
  const base = { instrument: 'crypto:BTCUSDT', market: 'crypto', timeframe: '1h' } as const;

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
});

describe('latestWindow', () => {
  it('is the usual page while there is no history below it', () => {
    expect(latestWindow('crypto', '1h', END)).toEqual(candleWindow('crypto', '1h', END));
  });

  it('reaches down to where the older pages begin, however long the tab sat idle', () => {
    const since = END - 3 * PAGE_SIZE * 3600;
    expect(latestWindow('crypto', '1h', END, since)).toEqual({ start: since, end: END });
  });

  it('never gets shorter than the usual page', () => {
    expect(latestWindow('crypto', '1h', END, END - 60)).toEqual(candleWindow('crypto', '1h', END));
  });
});

describe('the latest page with history below it', () => {
  const base = { instrument: 'crypto:BTCUSDT', market: 'crypto', timeframe: '1h' } as const;

  it('keeps its cache key, so loading the first older page costs no extra request', () => {
    expect(candlePageQueryOptions({ ...base, since: END }).queryKey).toEqual(candlePageQueryOptions(base).queryKey);
  });

  it('asks for the window from `since` when it refreshes', async () => {
    const fetch = vi.fn(() => Promise.resolve(new Response('{"t":[]}')));
    vi.stubGlobal('fetch', fetch);
    const since = Math.floor(Date.now() / 1000) - 3 * PAGE_SIZE * 3600;
    const { queryFn } = candlePageQueryOptions({ ...base, since });
    await (queryFn as (context: { signal: AbortSignal }) => Promise<unknown>)({ signal: new AbortController().signal });
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining(`&start=${since}&`), expect.anything());
  });
});

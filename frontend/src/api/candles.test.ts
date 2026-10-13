import { QueryClient } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { PAGE_SIZE, candlePageQueryOptions, getCandles, pageRange, type Candles } from './candles';

const END = 1_780_000_000;
const NOW = () => Math.floor(Date.now() / 1000);

afterEach(() => {
  vi.unstubAllGlobals();
});

// An answer of `count` candles one timeframe apart from `start` on.
function answer(start: number, count: number, step = 3600): Candles {
  const t = Array.from({ length: count }, (_, i) => start + i * step);
  return {
    meta: {
      instrument: 'crypto:BTCUSDT',
      timeframe: '1h',
      start,
      end: start + count * step,
      source: 'binance',
      feed: 'spot',
      fingerprint: 'x',
      count,
      gaps: [],
      gaps_total: 0,
    },
    t,
    o: t,
    h: t,
    l: t,
    c: t,
    v: t,
  };
}

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

  it('reaches the latest page down to the history below it, so a refresh opens no hole', () => {
    const since = END - (PAGE_SIZE + 300) * 3600;
    const last = { candles: answer(since, PAGE_SIZE + 299), at: END - 3600 };
    expect(pageRange({ ...base, since }, END, last)).toEqual({ start: since });
  });

  it('asks for the last candles while it does not know how many there are from `since`', () => {
    expect(pageRange({ ...base, since: END - 3600 }, END)).toEqual({ limit: PAGE_SIZE });
    const above = { candles: answer(END - 1800, 1), at: END - 60 };
    expect(pageRange({ ...base, since: END - 3600 }, END, above)).toEqual({ limit: PAGE_SIZE });
  });

  it('counts the candles of a stock from the last answer, not from the clock', () => {
    // AAPL 1m: the last answer, a minute ago, held the 500 session candles since `since`, two
    // days back. Counted by the clock, two days would be 2880 candles.
    const stock = { instrument: 'stock:AAPL', timeframe: '1m', maxCandles: 50_000 } as const;
    const since = END - 2 * 86_400;
    const last = { candles: answer(since, PAGE_SIZE, 60), at: END - 60 };
    expect(pageRange({ ...stock, since }, END, last)).toEqual({ start: since });
  });

  it('asks for the last candles again past two pages from `since`', () => {
    const since = END - 2000 * 3600;
    const at = END - 3600;
    expect(pageRange({ ...base, since }, END, { candles: answer(since, 998), at })).toEqual({ start: since });
    expect(pageRange({ ...base, since }, END, { candles: answer(since, 999), at })).toEqual({ limit: PAGE_SIZE });
    // Idle for ten hours at 1m: 600 more candles than the last answer held.
    const minutes = { ...base, timeframe: '1m', since } as const;
    const idle = { candles: answer(since, PAGE_SIZE, 60), at: END - 10 * 3600 };
    expect(pageRange(minutes, END, idle)).toEqual({ limit: PAGE_SIZE });
  });

  it('keeps a tenth of the maximum for a browser clock that runs behind', () => {
    const since = END - 2000 * 3600;
    const at = END - 3600;
    const small = { ...base, maxCandles: 1000, since };
    expect(pageRange(small, END, { candles: answer(since, 898), at })).toEqual({ start: since });
    expect(pageRange(small, END, { candles: answer(since, 899), at })).toEqual({ limit: PAGE_SIZE });
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

  // A client whose latest page came a minute ago and reached down to `since`.
  function clientWithLatest(since: number): QueryClient {
    const client = new QueryClient();
    const { queryKey } = candlePageQueryOptions(base);
    client.setQueryData(queryKey, answer(since, PAGE_SIZE), { updatedAt: Date.now() - 61_000 });
    return client;
  }

  it('refreshes the latest page from `since` with history below it', async () => {
    const fetch = vi.fn(() => Promise.resolve(new Response('{"t":[]}')));
    vi.stubGlobal('fetch', fetch);
    const since = NOW() - PAGE_SIZE * 3600;
    await clientWithLatest(since).fetchQuery(candlePageQueryOptions({ ...base, since }));
    expect(fetch).toHaveBeenCalledWith(
      `/api/v1/data/instruments/crypto%3ABTCUSDT/candles?timeframe=1h&start=${since}`,
      expect.anything(),
    );
  });

  it('asks for the last candles when the server, whose clock is ahead, finds too many from `since`', async () => {
    const tooMany = { type: 'https://candlestack.tech/problems/too-many-candles', status: 422, detail: 'Too many.' };
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(tooMany), { status: 422 }))
      .mockResolvedValueOnce(new Response('{"t":[1]}'));
    vi.stubGlobal('fetch', fetch);
    const since = NOW() - PAGE_SIZE * 3600;
    const page = await clientWithLatest(since).fetchQuery(candlePageQueryOptions({ ...base, since }));
    expect(page).toEqual({ t: [1] });
    expect(fetch).toHaveBeenLastCalledWith(
      `/api/v1/data/instruments/crypto%3ABTCUSDT/candles?timeframe=1h&limit=${PAGE_SIZE}`,
      expect.anything(),
    );
  });

  it('fails an older page that the server refuses, and other errors of the latest page', async () => {
    const tooMany = { type: 'https://candlestack.tech/problems/too-many-candles', status: 422, detail: 'Too many.' };
    const fetch = vi.fn(() => Promise.resolve(new Response(JSON.stringify(tooMany), { status: 422 })));
    vi.stubGlobal('fetch', fetch);
    await expect(new QueryClient().fetchQuery(candlePageQueryOptions({ ...base, end: END }))).rejects.toThrow(
      'Too many.',
    );
    fetch.mockResolvedValueOnce(new Response('{"detail":"Down."}', { status: 503 }));
    const since = NOW() - PAGE_SIZE * 3600;
    await expect(clientWithLatest(since).fetchQuery(candlePageQueryOptions({ ...base, since }))).rejects.toThrow(
      'Down.',
    );
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});

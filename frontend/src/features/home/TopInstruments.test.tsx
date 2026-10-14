import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider, createMemoryHistory, createRootRoute, createRouter } from '@tanstack/react-router';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { ApiError, instrumentSearchQueryOptions, type Instrument, type InstrumentSearchResult } from '@/api';
import { classes } from '@/test/markup';

import { TopInstruments } from './TopInstruments';

const DAY = 86_400;
const OCT_4 = 1_759_536_000; // 2025-10-04 00:00 UTC
// Ten daily candles, every one up.
const TEN_DAYS: Instrument['spark'] = Array.from({ length: 10 }, (_, i) => [
  OCT_4 + i * DAY,
  80_000 + i * 100,
  80_150 + i * 100,
  79_950 + i * 100,
  80_100 + i * 100,
]);

const BTC: Instrument = {
  id: 'crypto:BTCUSDT',
  symbol: 'BTCUSDT',
  name: 'Bitcoin / TetherUS',
  market: 'crypto',
  exchange: null,
  source: 'binance',
  feed: 'spot',
  base: 'BTC',
  quote: 'USDT',
  price: 83249.35,
  change_24h: 1.51,
  volume_24h: 1258811866,
  spark: TEN_DAYS,
};
const NVDA: Instrument = {
  id: 'stock:NVDA',
  symbol: 'NVDA',
  name: 'NVIDIA Corporation',
  market: 'stock',
  exchange: 'NASDAQ',
  source: 'alpaca',
  feed: 'sip',
  base: null,
  quote: null,
  price: 186.42,
  change_24h: -3.12,
  volume_24h: 612000000,
  spark: null,
};
const TOP: Instrument[] = [
  BTC,
  { ...BTC, id: 'crypto:ETHUSDT', symbol: 'ETHUSDT', price: 2499.82, change_24h: 1.6 },
  NVDA,
  { ...BTC, id: 'crypto:SOLUSDT', symbol: 'SOLUSDT', price: 106.67, change_24h: 0.001 },
  { ...NVDA, id: 'stock:TSLA', symbol: 'TSLA', exchange: 'NYSE', price: 431.18 },
];

const result = (items: Instrument[]): InstrumentSearchResult => ({
  items,
  count: items.length,
  total: 14567,
  offset: 0,
  unavailable: [],
});

// The rows' links need a router; a one-route router on "/", loaded first, is enough. The query
// client gets the answer of the request the home page makes (or none, or an error) beforehand.
async function render(prepare?: (client: QueryClient) => Promise<unknown> | void): Promise<string> {
  const rootRoute = createRootRoute({ component: TopInstruments });
  const router = createRouter({ routeTree: rootRoute, history: createMemoryHistory({ initialEntries: ['/'] }) });
  await router.load();
  // An error stays on screen instead of a new attempt on mount, which would show the loading state.
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, retryOnMount: false } } });
  await prepare?.(client);
  return renderToString(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

// The first five of the list's default order, the 24 h volume.
const { queryKey } = instrumentSearchQueryOptions({ q: '', limit: 5, offset: 0 });
const loaded = (items: Instrument[]) => (client: QueryClient) => void client.setQueryData(queryKey, result(items));

const rows = (html: string) =>
  [...html.matchAll(/<tr class="[^"]*border-b[^>]*>(.*?)<\/tr>/g)].map((match) => match[1] ?? '');
const cells = (row: string) => [...row.matchAll(/<td[^>]*>(.*?)<\/td>/g)].map((match) => match[0]);
// The text between the tags of server-rendered markup (a test helper, not a sanitizer).
const text = (html: string) =>
  [...html.matchAll(/>([^<]*)</g)]
    .map((match) => match[1] ?? '')
    .join('')
    .replaceAll('&amp;', '&');
const headers = (html: string) => [...html.matchAll(/<th [^>]*>.*?<\/th>/g)].map((match) => match[0]);

describe('TopInstruments', () => {
  it('shows a row for each of the five most traded, in their order', async () => {
    const all = rows(await render(loaded(TOP)));
    expect(all).toHaveLength(5);
    expect(all.map((row) => text(cells(row)[0] ?? ''))).toEqual(['BTCUSDT', 'ETHUSDT', 'NVDA', 'SOLUSDT', 'TSLA']);
  });

  it('links every row to its instrument, the symbol being its one tab stop', async () => {
    const html = await render(loaded(TOP));
    const all = rows(html);
    const links = all.map((row) => [...row.matchAll(/<a [^>]*>/g)].map((match) => match[0]));
    expect(links.map((each) => each.length)).toEqual([1, 1, 1, 1, 1]);
    expect(links.map(([link = '']) => link.match(/href="([^"]*)"/)?.[1])).toEqual([
      '/instrument/crypto%3ABTCUSDT',
      '/instrument/crypto%3AETHUSDT',
      '/instrument/stock%3ANVDA',
      '/instrument/crypto%3ASOLUSDT',
      '/instrument/stock%3ATSLA',
    ]);
    // stretched over the whole row
    expect(classes(all[0] ?? '', /<a [^>]*>/)).toEqual(expect.arrayContaining(['after:absolute', 'after:inset-0']));
    expect(classes(html, /<tr class="[^"]*border-b[^>]*>/)).toContain('relative');
  });

  it('shows the icon, the exchange, the candles, the price and the 24 h change', async () => {
    const [btc = '', , nvda = ''] = rows(await render(loaded(TOP)));
    expect(btc).toMatch(/<img [^>]*src="\/api\/v1\/data\/instruments\/crypto%3ABTCUSDT\/icon"[^>]*>.*>BTCUSDT<\/a>/);
    expect(cells(btc).map(text)).toEqual([
      'BTCUSDT',
      'Binance',
      '10 daily candles, +1.25%7 daily candles, +0.87%',
      '83,249.35+1.51%',
      '1.51%',
    ]);
    expect(cells(nvda).map(text)).toEqual(['NVDA', 'NASDAQ', 'No chart yetNo chart yet', '186.42−3.12%', '3.12%']);
  });

  it('colours the change and points its triangle up or down; 0.00 % is muted without one', async () => {
    const [btc = '', , nvda = '', flat = ''] = rows(await render(loaded(TOP)));
    const change = (row: string) => cells(row)[4] ?? '';
    expect(change(btc)).toContain('text-up');
    expect(change(btc)).toContain('d="M4 1 7.5 7h-7Z"');
    expect(change(nvda)).toContain('text-down');
    expect(change(nvda)).toContain('d="M4 7 .5 1h7Z"');
    expect(change(flat)).toContain('text-muted-foreground');
    expect(change(flat)).not.toContain('<svg');
    expect(text(change(flat))).toBe('0.00%');
    // on a phone, under the price, with its sign
    expect(cells(btc)[3]).toMatch(/<span class="[^"]*text-up[^"]*">\+1\.51%<\/span>/);
  });

  it('writes the symbol and the numbers in Geist Mono', async () => {
    const [btc = ''] = rows(await render(loaded(TOP)));
    expect(classes(btc, /<a [^>]*>BTCUSDT/)).toEqual(expect.arrayContaining(['font-mono', 'font-medium']));
    expect(classes(btc, /<span [^>]*>83,249.35/)).toContain('font-mono');
    expect(classes(btc, /<span [^>]*>\+1.51%/)).toContain('font-mono');
  });

  it('fits every width: fixed columns, the symbol takes the rest, phones get three columns', async () => {
    const html = await render(loaded(TOP));
    expect(classes(html, /<table [^>]*>/)).toContain('table-fixed');
    expect(headers(html).map(text)).toEqual(['Symbol', 'Exchange', '10d7d', 'PricePrice · 24h', '24h']);
    const [symbol, exchange, candles, price, change] = headers(html).map((th) => classes(th, /<th [^>]*>/));
    expect(symbol?.some((each) => each.startsWith('w-'))).toBe(false);
    expect(exchange).toEqual(expect.arrayContaining(['hidden', 'sm:table-cell', 'w-[96px]']));
    expect(candles).toEqual(expect.arrayContaining(['w-[60px]', 'sm:w-[136px]']));
    expect(price).toEqual(expect.arrayContaining(['w-[104px]', 'sm:w-[112px]']));
    expect(change).toEqual(expect.arrayContaining(['hidden', 'sm:table-cell', 'w-[92px]']));
    const [btc = ''] = rows(html);
    expect(btc).toContain('style="width:112px;height:32px"');
    expect(btc).toContain('style="width:44px;height:24px"');
    expect(classes(btc, /<a [^>]*>BTCUSDT</)).toContain('truncate');
  });

  it('sits on a solid background, so the page grid does not show through', async () => {
    const html = await render(loaded(TOP));
    expect(classes(html, /<div [^>]*>/)).toEqual(expect.arrayContaining(['rounded-lg', 'border', 'bg-background']));
  });
});

describe('TopInstruments states', () => {
  it('shows five ghost rows while loading, with no links', async () => {
    const html = await render();
    expect(rows(html)).toHaveLength(5);
    expect(html).not.toContain('<a ');
    expect(html).toMatch(/<table aria-hidden="true"/);
    expect(html).toContain('Loading instruments…');
  });

  it('says what went wrong in one line', async () => {
    const html = await render((client) =>
      client.prefetchQuery({ queryKey, queryFn: () => Promise.reject(new ApiError(0, 'Cannot reach the server.')) }),
    );
    expect(html).not.toContain('<table');
    expect(text(html)).toBe('No connection to the CandleStack server. Check your internet connection, then try again.');
    expect(classes(html, /<p [^>]*>/)).toContain('text-destructive');
  });

  it('says so when there is nothing to show', async () => {
    const html = await render(loaded([]));
    expect(html).not.toContain('<table');
    expect(text(html)).toBe('No instruments.');
  });
});

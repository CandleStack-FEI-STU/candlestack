import { RouterProvider, createMemoryHistory, createRootRoute, createRouter } from '@tanstack/react-router';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import type { Instrument } from '@/api';
import { classes } from '@/test/markup';

import { InstrumentTable } from './InstrumentTable';

const ITEMS: Instrument[] = [
  {
    id: 'crypto:BTCUSDT',
    symbol: 'BTCUSDT',
    name: 'Bitcoin / TetherUS',
    market: 'crypto',
    exchange: null,
    source: 'binance',
    feed: 'spot',
    base: 'BTC',
    quote: 'USDT',
  },
  {
    id: 'stock:AAPL',
    symbol: 'AAPL',
    name: 'Apple Inc.',
    market: 'stock',
    exchange: 'NASDAQ',
    source: 'alpaca',
    feed: 'iex',
    base: null,
    quote: null,
  },
];

// The rows' links need a router; a one-route router on "/", loaded first, is enough.
async function render(): Promise<string> {
  const rootRoute = createRootRoute({ component: () => <InstrumentTable items={ITEMS} /> });
  const router = createRouter({ routeTree: rootRoute, history: createMemoryHistory({ initialEntries: ['/'] }) });
  await router.load();
  return renderToString(<RouterProvider router={router} />);
}

const rows = (html: string) =>
  [...html.matchAll(/<tr class="relative[^>]*>(.*?)<\/tr>/g)].map((match) => match[1] ?? '');

describe('InstrumentTable', () => {
  it('shows a 32 px icon before the symbol of each row', async () => {
    const [btc, aapl] = rows(await render());
    expect(btc).toMatch(/<img [^>]*src="\/api\/v1\/data\/instruments\/crypto%3ABTCUSDT\/icon"[^>]*>.*>BTCUSDT<\/a>/);
    expect(aapl).toMatch(/<img [^>]*src="\/api\/v1\/data\/instruments\/stock%3AAAPL\/icon"[^>]*>.*>AAPL<\/a>/);
    expect(btc).toMatch(/<img [^>]*width="32"/);
  });

  it('keeps long names and symbols inside the table at every width', async () => {
    const html = await render();
    const [btc = ''] = rows(html);
    // Fixed column widths: the cells truncate their text instead of widening the table.
    expect(classes(html, /<table [^>]*>/)).toContain('table-fixed');
    expect(classes(btc, /<span [^>]*>Bitcoin/)).toContain('truncate');
    expect(classes(btc, /<a [^>]*>BTCUSDT</)).toContain('truncate');
  });

  it('shows cut text in full on hover', async () => {
    const [btc = '', aapl = ''] = rows(await render());
    expect(btc).toMatch(/<a [^>]*title="BTCUSDT"[^>]*>BTCUSDT<\/a>/);
    expect(btc).toMatch(/<span title="Bitcoin \/ TetherUS"[^>]*>Bitcoin/);
    // The market and exchange: in their columns, and under the name on a phone.
    expect(btc).toMatch(/<span title="crypto · Binance"[^>]*>crypto · Binance</);
    expect(aapl).toMatch(/<td title="stock"[^>]*>stock</);
    expect(aapl).toMatch(/<td title="NASDAQ"[^>]*>NASDAQ</);
  });

  it('keeps the symbol the only link of a row, so the row stays one click target', async () => {
    const all = rows(await render());
    expect(all).toHaveLength(2);
    for (const row of all) {
      expect(row.match(/<a /g)).toHaveLength(1);
    }
  });
});

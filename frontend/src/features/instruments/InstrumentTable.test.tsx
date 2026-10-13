import { RouterProvider, createMemoryHistory, createRootRoute, createRouter } from '@tanstack/react-router';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import type { Instrument } from '@/api';

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

  it('lets the name, not the table, give way on a phone', async () => {
    const [btc] = rows(await render());
    // w-full with max-w-0: the name cell takes the width left and truncates instead of widening
    // the table; from sm up it is at most 16rem, as before.
    expect(btc).toMatch(/<td class="[^"]*w-full max-w-0[^"]*sm:max-w-\[16rem\]"><span class="block truncate">Bitcoin/);
    expect(btc).toMatch(/<a [^>]*class="max-w-32 truncate [^"]*sm:max-w-none"[^>]*>BTCUSDT<\/a>/);
  });

  it('keeps the symbol the only link of a row, so the row stays one click target', async () => {
    const all = rows(await render());
    expect(all).toHaveLength(2);
    for (const row of all) {
      expect(row.match(/<a /g)).toHaveLength(1);
    }
  });
});

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider, createMemoryHistory, createRootRoute, createRouter } from '@tanstack/react-router';
import type { ComponentProps } from 'react';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { InstrumentList } from './InstrumentList';

// The list needs a query client and a router; a one-route router on the given URL, loaded first.
async function render(url: string, props: ComponentProps<typeof InstrumentList>): Promise<string> {
  const rootRoute = createRootRoute({ component: () => <InstrumentList {...props} /> });
  const router = createRouter({ routeTree: rootRoute, history: createMemoryHistory({ initialEntries: [url] }) });
  await router.load();
  const client = new QueryClient();
  return renderToString(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe('InstrumentList', () => {
  it('says why a market and an exchange it does not trade on find nothing, with a way out', async () => {
    const html = await render('/?q=a&market=crypto&exchange=NYSE&page=2', {
      query: 'a',
      market: 'crypto',
      exchange: 'NYSE',
      sort: undefined,
      page: 2,
    });
    expect(html).toContain('No crypto pairs on NYSE');
    expect(html).toContain('NYSE lists stocks only.');
    expect(html).toMatch(/<a [^>]*href="\/\?q=a&amp;market=crypto"[^>]*>Show all exchanges<\/a>/);
    expect(html).not.toContain('Loading');
  });

  it('loads the list for a market and an exchange it trades on', async () => {
    const html = await render('/?market=crypto&exchange=BINANCE', {
      query: '',
      market: 'crypto',
      exchange: 'BINANCE',
      sort: undefined,
      page: 1,
    });
    expect(html).toContain('Loading instruments…');
  });
});

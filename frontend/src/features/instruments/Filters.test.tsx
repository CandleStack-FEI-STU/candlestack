import { RouterProvider, createMemoryHistory, createRootRoute, createRouter } from '@tanstack/react-router';
import type { ComponentProps } from 'react';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { Filters } from './Filters';

// The button needs a router; a one-route router on "/", loaded first, is enough.
async function render(props: ComponentProps<typeof Filters>): Promise<string> {
  const rootRoute = createRootRoute({ component: () => <Filters {...props} /> });
  const router = createRouter({ routeTree: rootRoute, history: createMemoryHistory({ initialEntries: ['/'] }) });
  await router.load();
  return renderToString(<RouterProvider router={router} />);
}

describe('Filters', () => {
  it('is one closed button that sums up the filters', async () => {
    const html = await render({ market: 'stock', exchange: 'NYSE' });
    expect(html).toContain('aria-label="Filters: Stocks · NYSE"');
    expect(html).toContain('aria-haspopup="dialog"');
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain('h-[34px] w-[200px]');
    expect(html).not.toContain('role="listbox"');
  });

  it('says "All instruments" without filters', async () => {
    expect(await render({ market: undefined, exchange: undefined })).toContain('>All instruments</span>');
  });
});

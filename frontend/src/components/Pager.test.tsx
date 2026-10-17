import { RouterProvider, createMemoryHistory, createRootRoute, createRouter } from '@tanstack/react-router';
import type { ComponentProps } from 'react';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { Pager } from './Pager';

// The pager's links need a router; a one-route router on "/", loaded first, is enough.
async function render(props: Omit<ComponentProps<typeof Pager>, 'from'>): Promise<string> {
  const rootRoute = createRootRoute({ component: () => <Pager {...props} from="/instruments" /> });
  const router = createRouter({ routeTree: rootRoute, history: createMemoryHistory({ initialEntries: ['/'] }) });
  await router.load();
  // React marks where text pieces meet with <!-- -->; the text reads better without.
  return renderToString(<RouterProvider router={router} />).replaceAll('<!-- -->', '');
}

const links = (html: string) => [...html.matchAll(/<a [^>]*>([^<]+)<\/a>/g)].map((match) => match[1]);
const labels = (html: string) =>
  [...html.matchAll(/<span aria-disabled="true"[^>]*>([^<]+)<\/span>/g)].map((m) => m[1]);

describe('Pager', () => {
  it('links to the pages that exist and labels the ones that do not', async () => {
    const html = await render({ page: 1, hasNext: true, pages: 3, loading: false });
    expect(links(html)).toEqual(['Next']);
    expect(labels(html)).toEqual(['Previous']);
    expect(html).toContain('Page 1 of 3');
  });

  it('waits while a page loads, so a second click cannot skip ahead', async () => {
    const html = await render({ page: 2, hasNext: true, pages: 3, loading: true });
    expect(links(html)).toEqual([]);
    expect(labels(html)).toEqual(['Previous', 'Next']);
  });
});

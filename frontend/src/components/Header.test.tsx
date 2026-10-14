import {
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from '@tanstack/react-router';
import { renderToString } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';

import { Header } from '@/components/Header';
import { classes } from '@/test/markup';

// The theme reads the page's <html>, which a server render has not.
vi.mock('@/theme', () => ({ useTheme: () => ({ theme: 'dark', toggle: () => undefined }) }));

// The header over the app's three pages, on the given URL, loaded first.
async function render(url: string): Promise<string> {
  const rootRoute = createRootRoute({ component: Header });
  const page = (path: string) => createRoute({ getParentRoute: () => rootRoute, path });
  const routeTree = rootRoute.addChildren([page('/'), page('/instruments'), page('/instrument/$id')]);
  const router = createRouter({ routeTree, history: createMemoryHistory({ initialEntries: [url] }) });
  await router.load();
  return renderToString(<RouterProvider router={router} />);
}

const navItem = (html: string, name: string) => classes(html, new RegExp(`<a [^>]*>${name}</a>`));
const isOn = (html: string, name: string) => navItem(html, name).includes('font-medium');

describe('Header', () => {
  it('marks Product on the home page', async () => {
    const html = await render('/');
    expect(isOn(html, 'Product')).toBe(true);
    expect(isOn(html, 'Instruments')).toBe(false);
  });

  it('marks Instruments on the list and on an instrument', async () => {
    for (const url of ['/instruments?q=btc', '/instrument/crypto:BTCUSDT']) {
      const html = await render(url);
      expect(isOn(html, 'Instruments')).toBe(true);
      expect(isOn(html, 'Product')).toBe(false);
    }
  });

  it('opens the API docs of its own host in a new tab', async () => {
    const tag = /<a [^>]*>API<\/a>/.exec(await render('/'))?.[0];
    expect(tag).toContain('href="/api/v1/docs"');
    expect(tag).toContain('target="_blank"');
    expect(tag).toContain('rel="noopener"');
  });

  it('has Sign in and Try Backtest as plain buttons, Sign in hidden below md', async () => {
    const html = await render('/');
    expect(html).toMatch(/<button [^>]*type="button"[^>]*>Sign in<\/button>/);
    expect(html).toMatch(/<button [^>]*type="button"[^>]*>Try Backtest<\/button>/);
    expect(classes(html, /<button [^>]*>Sign in/)).toContain('max-md:hidden');
  });

  it('hovers Sign in with the full surface in the dark theme too', async () => {
    const signIn = classes(await render('/'), /<button [^>]*>Sign in/);
    expect(signIn).toContain('dark:hover:bg-accent');
    expect(signIn).not.toContain('dark:hover:bg-accent/50');
  });

  it('has no search box', async () => {
    expect(await render('/instrument/crypto:BTCUSDT')).not.toContain('<input');
  });
});

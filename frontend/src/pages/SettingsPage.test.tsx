// @vitest-environment jsdom
import { cleanup, screen, within } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { ARSEN, sessionWithPreferences, stubApi } from '@/test/api';
import { renderApp, warmUpSettings } from '@/test/app';

beforeAll(warmUpSettings);

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const tabs = () => within(screen.getByRole('navigation', { name: 'Settings sections' }));

describe('Settings', () => {
  it('opens Profile from /settings, under the title', async () => {
    stubApi(sessionWithPreferences(ARSEN));
    const { router } = await renderApp('/settings');
    expect(router.state.location.pathname).toBe('/settings/profile');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Settings');
    expect(screen.getByText('Your account and how new backtests start')).toBeDefined();
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe('Profile');
    expect(document.title).toBe('Settings · CandleStack');
  });

  it('opens Profile for a section it does not know', async () => {
    stubApi(sessionWithPreferences(ARSEN));
    const { router } = await renderApp('/settings/billing');
    expect(router.state.location.pathname).toBe('/settings/profile');
  });

  it('has the sections as tabs, each a link, the open one marked', async () => {
    stubApi(sessionWithPreferences(ARSEN));
    await renderApp('/settings/appearance');
    const links = tabs().getAllByRole('link');
    expect(links.map((link) => [link.textContent, link.getAttribute('href')])).toEqual([
      ['Profile', '/settings/profile'],
      ['Sign-in', '/settings/sign-in'],
      ['Backtest defaults', '/settings/backtest-defaults'],
      ['Appearance', '/settings/appearance'],
      ['Data and storage', '/settings/data-and-storage'],
      ['API and MCP', '/settings/api-and-mcp'],
      ['Account', '/settings/account'],
    ]);
    expect(links.map((link) => link.getAttribute('aria-current'))).toEqual([
      null,
      null,
      null,
      'page',
      null,
      null,
      null,
    ]);
  });

  it('shows one section at a time and switches with the tabs; the sidebar keeps Settings', async () => {
    stubApi(sessionWithPreferences(ARSEN));
    const { router } = await renderApp('/settings/profile');
    await userEvent.setup().click(tabs().getByRole('link', { name: 'Data and storage' }));
    await vi.waitFor(() => expect(router.state.location.pathname).toBe('/settings/data-and-storage'));
    expect(screen.getAllByRole('heading', { level: 2 }).map((heading) => heading.textContent)).toEqual([
      'Data and storage',
    ]);
    const sidebar = within(screen.getByRole('navigation', { name: 'Workspace' }));
    expect(sidebar.getByRole('link', { name: 'Settings' }).getAttribute('aria-current')).toBe('page');
  });

  it('loads the preferences before the sections that show them', async () => {
    const fetch = stubApi(sessionWithPreferences(ARSEN));
    await renderApp('/settings/backtest-defaults');
    expect(fetch).toHaveBeenCalledWith('/api/v1/me/preferences', expect.anything());
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe('Backtest defaults');
  });

  it('shows where the market data comes from', async () => {
    stubApi(sessionWithPreferences(ARSEN));
    await renderApp('/settings/data-and-storage');
    const card = within(screen.getByRole('region', { name: 'Data and storage' }));
    expect(card.getByText('Market data').textContent).toBe('Market dataDelayed 15 min');
    expect(card.getByText('Alpaca, SIP feed')).toBeDefined();
  });

  it('shows the API keys and the MCP server as coming soon, with the API docs of this host', async () => {
    stubApi(sessionWithPreferences(ARSEN));
    await renderApp('/settings/api-and-mcp');
    const keys = within(screen.getByRole('region', { name: 'API keys' }));
    expect(keys.getByText('Coming soon')).toBeDefined();
    const docs = keys.getByRole('link', { name: 'API docs' });
    expect(docs.getAttribute('href')).toBe('/api/v1/docs');
    expect(docs.getAttribute('target')).toBe('_blank');
    const mcp = within(screen.getByRole('region', { name: 'MCP server' }));
    expect(mcp.getByText('Coming soon')).toBeDefined();
    expect(mcp.getByText(`${window.location.origin}/mcp`)).toBeDefined();
  });
});

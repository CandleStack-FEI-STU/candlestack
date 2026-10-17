import { QueryClient } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { DEFAULT_PREFERENCES, sentBody, stubApi } from '@/test/api';

import { preferencesQueryOptions, saveBacktestDefaults, updateAppearance } from './preferences';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('preferences', () => {
  it('are read under the account, so signing out forgets them', async () => {
    stubApi({ 'GET /api/v1/me/preferences': { status: 200, body: DEFAULT_PREFERENCES } });
    expect(preferencesQueryOptions().queryKey).toEqual(['account', 'preferences']);
    await expect(new QueryClient().fetchQuery(preferencesQueryOptions())).resolves.toEqual(DEFAULT_PREFERENCES);
  });

  it('save the backtest defaults whole', async () => {
    const defaults = { ...DEFAULT_PREFERENCES.backtest_defaults, timeframe: '1h' as const };
    const fetch = stubApi({ 'PUT /api/v1/me/preferences/backtest-defaults': { status: 200, body: defaults } });
    await expect(saveBacktestDefaults(defaults)).resolves.toEqual(defaults);
    expect(sentBody(fetch, 'PUT /api/v1/me/preferences/backtest-defaults')).toEqual(defaults);
  });

  it('change only the appearance settings given', async () => {
    const appearance = { ...DEFAULT_PREFERENCES.appearance, theme: 'light' as const };
    const fetch = stubApi({ 'PATCH /api/v1/me/preferences/appearance': { status: 200, body: appearance } });
    await expect(updateAppearance({ theme: 'light' })).resolves.toEqual(appearance);
    expect(sentBody(fetch, 'PATCH /api/v1/me/preferences/appearance')).toEqual({ theme: 'light' });
  });
});

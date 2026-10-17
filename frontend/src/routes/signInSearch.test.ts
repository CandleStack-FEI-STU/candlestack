import { describe, expect, it } from 'vitest';

import { appPath, validateSignInSearch } from './signInSearch';

// The router passes the raw search object; SearchSchemaInput is only a type marker.
type RawSearch = Parameters<typeof validateSignInSearch>[0];
const validate = (search: Record<string, unknown>) => validateSignInSearch(search as RawSearch);

describe('appPath', () => {
  it('keeps a path of the app with its search and hash', () => {
    expect(appPath('/dashboard')).toBe('/dashboard');
    expect(appPath('/instruments?q=btc&page=2')).toBe('/instruments?q=btc&page=2');
    expect(appPath('/instrument/crypto:BTCUSDT#chart')).toBe('/instrument/crypto:BTCUSDT#chart');
  });

  it('refuses every address that leaves the app', () => {
    for (const value of [
      'https://evil.example',
      '//evil.example/dashboard',
      String.raw`/\evil.example`,
      '/\t/evil.example',
      'javascript:alert(1)',
      'dashboard',
      '',
    ]) {
      expect(appPath(value)).toBeUndefined();
    }
  });

  it('refuses the sign-in page itself and the API', () => {
    expect(appPath('/signin?next=/models')).toBeUndefined();
    expect(appPath('/api/v1/docs')).toBeUndefined();
    expect(appPath('/api')).toBeUndefined();
  });

  it('refuses what is not a string', () => {
    expect(appPath(42)).toBeUndefined();
    expect(appPath({ to: '/dashboard' })).toBeUndefined();
  });

  it('normalizes the path', () => {
    expect(appPath('/models/../settings')).toBe('/settings');
  });
});

describe('validateSignInSearch', () => {
  it('keeps a safe next and a known error', () => {
    expect(validate({ next: '/models', error: 'denied' })).toEqual({ next: '/models', error: 'denied' });
    expect(validate({ error: 'failed' })).toEqual({ next: undefined, error: 'failed' });
  });

  it('sets a dropped value to undefined, so the router cannot keep the raw one', () => {
    const search = validate({ next: 'https://evil.example', error: 'oops' });
    expect(search).toEqual({ next: undefined, error: undefined });
    expect(Object.keys(search)).toEqual(['next', 'error']);
  });
});

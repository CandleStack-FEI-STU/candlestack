import { afterEach, describe, expect, it, vi } from 'vitest';

import { ARSEN, NOT_SIGNED_IN, session, stubApi } from '@/test/api';

import { getMe, signInUrl, signOut } from './accounts';
import { ApiError } from './client';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('getMe', () => {
  it('returns the signed-in user', async () => {
    stubApi(session(ARSEN));
    await expect(getMe()).resolves.toEqual(ARSEN);
  });

  it('reads 401 not-signed-in as signed out, not as an error', async () => {
    stubApi({ 'GET /api/v1/me': NOT_SIGNED_IN });
    await expect(getMe()).resolves.toBeNull();
  });

  it('passes any other failure on', async () => {
    stubApi({ 'GET /api/v1/me': { status: 503, body: { detail: 'Down for a minute.' } } });
    await expect(getMe()).rejects.toBeInstanceOf(ApiError);
  });
});

describe('signInUrl', () => {
  it('starts at the provider of the API, without next for the default landing', () => {
    expect(signInUrl('github')).toBe('/api/v1/auth/github/start');
    expect(signInUrl('google')).toBe('/api/v1/auth/google/start');
  });

  it('passes next encoded, search included', () => {
    expect(signInUrl('github', '/instruments?q=btc')).toBe('/api/v1/auth/github/start?next=%2Finstruments%3Fq%3Dbtc');
  });
});

describe('signOut', () => {
  it('posts to the sign-out endpoint', async () => {
    const fetch = stubApi({ 'POST /api/v1/auth/sign-out': { status: 204 } });
    await expect(signOut()).resolves.toBeUndefined();
    expect(fetch).toHaveBeenCalledOnce();
  });

  it('reads 401 as signed out already, not as an error', async () => {
    stubApi({ 'POST /api/v1/auth/sign-out': NOT_SIGNED_IN });
    await expect(signOut()).resolves.toBeUndefined();
  });

  it('passes any other failure on', async () => {
    for (const status of [403, 503]) {
      stubApi({ 'POST /api/v1/auth/sign-out': { status, body: { detail: 'No.' } } });
      await expect(signOut()).rejects.toMatchObject({ status });
    }
  });
});

import { queryOptions } from '@tanstack/react-query';

import { ApiError, apiUrl, get, post } from './client';
import type { components } from './schema';

export type Me = components['schemas']['MeOut'];
export type DeniedSignIn = components['schemas']['DeniedSignInOut'];
export type Provider = components['schemas']['Provider'];

// GET /api/v1/me: the signed-in user, or null when this browser has no session. The API answers
// that with 401 (problem not-signed-in), which is a state of the app, not an error.
export async function getMe(signal?: AbortSignal): Promise<Me | null> {
  try {
    return await get<Me>('/v1/me', signal);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

// The user's own data sits under ['account', ...], so signing out knows what to forget. Every
// page shares this one entry: the header, the guards and the signed-in pages. Fresh until the
// app changes it: signing in is a full page load, signing out sets it to null.
export function meQueryOptions() {
  return queryOptions({
    queryKey: ['account', 'me'],
    queryFn: ({ signal }) => getMe(signal),
    staleTime: Infinity,
  });
}

// GET /api/v1/auth/denied: the account the beta list just turned away, for the sign-in page.
// Asked once per denied sign-in: the route's loader asks, the page reads the answer. It does not
// change while the page is open, and a failed answer is not asked again when the page mounts (the
// page then offers the buttons).
export function deniedSignInQueryOptions() {
  return queryOptions({
    queryKey: ['auth', 'denied'],
    queryFn: ({ signal }) => get<DeniedSignIn>('/v1/auth/denied', signal),
    staleTime: Infinity,
    retryOnMount: false,
  });
}

// Where the browser goes to sign in: the API redirects to the provider and, once it returns,
// to `next` (a path of the app; the API's default is /dashboard). A full page navigation, not
// a fetch: the provider's page cannot load in the app.
export function signInUrl(provider: Provider, next?: string): string {
  const query = next === undefined ? '' : `?${new URLSearchParams({ next }).toString()}`;
  return apiUrl(`/v1/auth/${provider}/start${query}`);
}

// POST /api/v1/auth/sign-out: ends this browser's session. A 401 says it had already ended:
// signed out all the same.
export async function signOut(): Promise<void> {
  try {
    await post('/v1/auth/sign-out');
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return;
    throw error;
  }
}

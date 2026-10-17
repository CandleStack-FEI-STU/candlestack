import { queryOptions } from '@tanstack/react-query';

import { ApiError, apiUrl, del, get, patch, post } from './client';
import type { components } from './schema';

export type Me = components['schemas']['MeOut'];
export type DeniedSignIn = components['schemas']['DeniedSignInOut'];
export type Provider = components['schemas']['Provider'];
type MeUpdate = components['schemas']['MeUpdate'];

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

// Where the browser goes to add a sign-in method (Settings, Sign-in): the same start with
// intent=connect. The API returns to `next`, with ?error=taken when the provider's account
// already signs in to another user, or ?error=failed.
export function connectUrl(provider: Provider, next: string): string {
  return apiUrl(`/v1/auth/${provider}/start?${new URLSearchParams({ intent: 'connect', next }).toString()}`);
}

// A 401 on ending a session says it had already ended: signed out all the same.
async function endSession(request: () => Promise<void>): Promise<void> {
  try {
    await request();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return;
    throw error;
  }
}

// POST /api/v1/auth/sign-out: ends this browser's session.
export const signOut = () => endSession(() => post('/v1/auth/sign-out'));

// POST /api/v1/auth/sign-out-everywhere: ends every session of the user, this one included.
export const signOutEverywhere = () => endSession(() => post('/v1/auth/sign-out-everywhere'));

// PATCH /api/v1/me: changes the display name; the API trims it and answers with the user.
export const updateMe = (update: MeUpdate) => patch<Me>('/v1/me', update);

// DELETE /api/v1/me: deletes the account with everything it owns and ends all its sessions.
export const deleteMe = () => del('/v1/me');

// DELETE /api/v1/me/sign-in-methods/{provider}. The account's last method cannot go: 409 with
// the problem last-sign-in-method.
export const disconnectSignInMethod = (provider: Provider) => del(`/v1/me/sign-in-methods/${provider}`);

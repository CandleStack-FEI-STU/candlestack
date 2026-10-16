import type { QueryClient } from '@tanstack/react-query';
import { redirect, type ParsedLocation } from '@tanstack/react-router';

import { meQueryOptions } from '@/api';

import type { SignInSearch } from './signInSearch';

// The guards of the routes that depend on the session. Both read the user from the cache the
// header shares, so a page change costs no request once it is known.

// The signed-in pages: without a session, the sign-in page, which returns to the page asked for.
export async function requireSignedIn({
  queryClient,
  location,
}: {
  queryClient: QueryClient;
  location: ParsedLocation;
}) {
  const me = await queryClient.ensureQueryData(meQueryOptions());
  if (me === null) throw redirect({ to: '/signin', search: { next: location.href } });
}

// The sign-in page: an open session skips it and goes where the sign-in would have led.
export async function skipSignInWhenSignedIn({
  queryClient,
  search,
}: {
  queryClient: QueryClient;
  search: SignInSearch;
}) {
  const me = await queryClient.ensureQueryData(meQueryOptions());
  if (me !== null) throw redirect({ href: search.next ?? '/dashboard' });
}

import type { SearchSchemaInput } from '@tanstack/react-router';

// /signin?next=/backtests&error=denied: where to go after signing in, and how the last attempt
// ended when the API sent the browser back here (docs/frontend.md, Sign-in).
export type SignInSearch = { next?: string; error?: SignInError };

// denied: the account is not on the beta list. failed: the provider or the API failed; the page
// simply offers the buttons again.
type SignInError = 'denied' | 'failed';

// Any absolute URL works as a base: only paths that stay on it are kept.
const BASE = 'https://app.invalid';

// A path of this app, or undefined. Only a path on the app's own origin: an address elsewhere
// ("https://evil.example", "//evil.example", "/\evil.example") would turn signing in into an
// open redirect. Not /signin itself (a loop) and not the API. The path comes back normalized,
// with its search and hash.
export function appPath(value: unknown): string | undefined {
  if (typeof value !== 'string' || !value.startsWith('/')) return undefined;
  const url = URL.parse(value, BASE);
  if (url === null || url.origin !== BASE) return undefined;
  if (url.pathname === '/signin' || url.pathname === '/api' || url.pathname.startsWith('/api/')) return undefined;
  return `${url.pathname}${url.search}${url.hash}`;
}

function parseError(value: unknown): SignInError | undefined {
  return value === 'denied' || value === 'failed' ? value : undefined;
}

// A broken or foreign value is dropped, never followed. Both keys are always set, undefined
// included: the router keeps search params a route does not return, so leaving one out would let
// the raw value through to the page.
export function validateSignInSearch(search: { next?: unknown; error?: unknown } & SearchSchemaInput): SignInSearch {
  return { next: appPath(search.next), error: parseError(search.error) };
}

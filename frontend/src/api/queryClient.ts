import { QueryClient } from '@tanstack/react-query';

import { ApiError } from './client';

// One retry, and only when the request may succeed right away: no answer at all (status 0) or
// a gateway error (502, 504). Never when the server says how long to wait (Retry-After, as on
// 429 and 503): retrying sooner ignores it and spends the 60 per minute budget. Never on other
// 4xx: a bad request stays bad.
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= 1) return false;
  if (!(error instanceof ApiError)) return false;
  if (error.retryAfter !== undefined) return false;
  return error.status === 0 || error.status === 502 || error.status === 504;
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Market data of a minute ago is fine; this keeps us far from the 60 requests per minute.
      staleTime: 60_000,
      refetchOnWindowFocus: false,
      retry: shouldRetry,
    },
  },
});

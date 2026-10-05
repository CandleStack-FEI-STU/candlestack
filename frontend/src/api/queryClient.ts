import { QueryClient } from '@tanstack/react-query'

import { ApiError } from './client'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Market data of a minute ago is fine; this keeps us far from the 60 requests per minute.
      staleTime: 60_000,
      refetchOnWindowFocus: false,
      // Retry once on network errors and 5xx. Never on 4xx: a 429 says to wait, and a bad
      // request stays bad.
      retry: (failureCount, error) => {
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false
        return failureCount < 1
      },
    },
  },
})

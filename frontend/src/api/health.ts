import { useQuery } from '@tanstack/react-query'

import { ApiError, get } from './client'
import type { components } from './schema'

export type Health = components['schemas']['Health']

// GET /api/health. It answers 503 with the same body when Redis is down, which is still a
// health report, not a failure of the request.
export async function getHealth(signal?: AbortSignal): Promise<Health> {
  try {
    return await get<Health>('/health', signal)
  } catch (error) {
    if (error instanceof ApiError && error.status === 503 && error.body) return error.body as Health
    throw error
  }
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => getHealth(signal),
    // Not rate-limited; once a minute is enough for a status dot.
    refetchInterval: 60_000,
  })
}

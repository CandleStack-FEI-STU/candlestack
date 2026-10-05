// The only place that calls fetch. Every request to the CandleStack API goes through here, so
// when the API changes (#104-#109) the fix is in src/api/ and nowhere else.

// Relative on purpose: in prod the page and the API share a host, in dev the Vite proxy
// forwards /api to https://app.candlestack.tech (vite.config.ts).
const BASE = '/api'

// An error answer of the API. Errors are RFC 9457 problem+json: `detail` says in plain words
// what went wrong and is fine to show to the user.
export class ApiError extends Error {
  readonly status: number
  // Seconds to wait, from the Retry-After header (429 rate-limited, 503 source-unavailable).
  readonly retryAfter?: number
  // The problem slug, e.g. "rate-limited", from https://candlestack.tech/problems/<slug>.
  readonly problem?: string
  readonly body: unknown

  constructor(status: number, message: string, body: unknown, retryAfter?: number, problem?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
    this.retryAfter = retryAfter
    this.problem = problem
  }
}

type Problem = { type?: string; title?: string; detail?: string }

export async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  let res: Response
  try {
    res = await fetch(BASE + path, { signal, headers: { Accept: 'application/json' } })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new ApiError(0, 'Cannot reach the server. Check your connection.', null)
  }

  const body: unknown = await res.json().catch(() => null)
  if (res.ok) return body as T

  const problem = (body ?? {}) as Problem
  const retryAfter = Number(res.headers.get('Retry-After')) || undefined
  const message =
    problem.detail ?? problem.title ?? `The server answered ${res.status} ${res.statusText}`.trim()
  const slug = problem.type?.split('/problems/')[1]
  throw new ApiError(res.status, message, body, retryAfter, slug)
}

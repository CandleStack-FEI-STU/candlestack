// The only place that calls fetch. Every request to the CandleStack API goes through here, so
// when the API changes (#104-#109) the fix is in src/api/ and nowhere else.

// Relative on purpose: in prod the page and the API share a host, in dev the Vite proxy
// forwards /api to https://app.candlestack.tech (vite.config.ts).
const BASE = '/api';

// An error answer of the API, or no answer at all (status 0). Errors are RFC 9457
// problem+json: `detail` says in plain words what went wrong and is fine to show to the user.
export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;
  // Seconds to wait, from the Retry-After header (429 rate-limited, 503 source-unavailable).
  readonly retryAfter?: number;
  // The problem slug, e.g. "rate-limited", from https://candlestack.tech/problems/<slug>.
  readonly problem?: string;

  constructor(
    status: number,
    message: string,
    details: { body?: unknown; retryAfter?: number; problem?: string } = {},
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = details.body ?? null;
    this.retryAfter = details.retryAfter;
    this.problem = details.problem;
  }
}

// Retry-After is either whole seconds ("30", "0") or an HTTP date. Anything else: no hint.
export function parseRetryAfter(value: string | null, now: number = Date.now()): number | undefined {
  if (value === null || value.trim() === '') return undefined;
  const text = value.trim();
  if (/^\d+$/.test(text)) return Number(text);
  // An HTTP date has a day and a month name; without letters, Date.parse would also accept "-5".
  if (!/[a-z]/i.test(text)) return undefined;
  const date = Date.parse(text);
  if (Number.isNaN(date)) return undefined;
  return Math.max(0, Math.ceil((date - now) / 1000));
}

type Problem = { type?: unknown; title?: unknown; detail?: unknown };

function errorFromResponse(res: Response, body: unknown): ApiError {
  const problem: Problem = typeof body === 'object' && body !== null ? body : {};
  const text = (value: unknown) => (typeof value === 'string' && value !== '' ? value : undefined);
  const message = text(problem.detail) ?? text(problem.title) ?? `The server answered ${res.status}.`;
  const slug = text(problem.type)?.split('/problems/')[1];
  return new ApiError(res.status, message, {
    body,
    retryAfter: parseRetryAfter(res.headers.get('Retry-After')),
    problem: slug,
  });
}

async function readJson(res: Response): Promise<{ ok: true; body: unknown } | { ok: false }> {
  try {
    return { ok: true, body: await res.json() };
  } catch {
    return { ok: false };
  }
}

export async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, { signal, headers: { Accept: 'application/json' } });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError(0, 'Cannot reach the server. Check your connection.');
  }

  const json = await readJson(res);
  if (!res.ok) throw errorFromResponse(res, json.ok ? json.body : null);
  // A 2xx that is not JSON (an HTML page on an /api path, say) is not data the page can use.
  if (!json.ok) throw new ApiError(res.status, 'The server sent an answer the app cannot read.');
  return json.body as T;
}

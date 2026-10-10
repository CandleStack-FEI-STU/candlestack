import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError, get, parseRetryAfter } from './client';

function answer(status: number, body: string, headers: Record<string, string> = {}) {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve(new Response(body, { status, headers }))),
  );
}

async function errorOf(promise: Promise<unknown>): Promise<ApiError> {
  const error: unknown = await promise.then(
    () => undefined,
    (reason: unknown) => reason,
  );
  if (!(error instanceof ApiError)) throw new Error(`expected an ApiError, got ${String(error)}`);
  return error;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('get', () => {
  it('returns the JSON body of a 2xx', async () => {
    answer(200, '{"status":"ok"}', { 'Content-Type': 'application/json' });
    await expect(get('/health')).resolves.toEqual({ status: 'ok' });
    expect(fetch).toHaveBeenCalledWith(
      '/api/health',
      expect.objectContaining({ headers: { Accept: 'application/json' } }),
    );
  });

  it('maps problem+json to an ApiError with detail, slug and Retry-After', async () => {
    const problem = {
      type: 'https://candlestack.tech/problems/rate-limited',
      title: 'Too many requests',
      status: 429,
      detail: 'Over 60 requests this minute.',
    };
    answer(429, JSON.stringify(problem), { 'Retry-After': '17' });
    const error = await errorOf(get('/data/candles'));
    expect(error).toMatchObject({ status: 429, message: problem.detail, problem: 'rate-limited', retryAfter: 17 });
    expect(error.body).toEqual(problem);
  });

  it('falls back to the title, then to the status, for the message', async () => {
    answer(404, '{"title":"Not found"}');
    expect((await errorOf(get('/x'))).message).toBe('Not found');
    answer(502, '<html>Bad gateway</html>');
    const error = await errorOf(get('/x'));
    expect(error).toMatchObject({ status: 502, message: 'The server answered 502.', body: null });
  });

  it('throws an ApiError with status 0 when there is no answer', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    );
    const error = await errorOf(get('/health'));
    expect(error.status).toBe(0);
    expect(error.retryAfter).toBeUndefined();
  });

  it('passes an abort through unchanged', async () => {
    const controller = new AbortController();
    controller.abort();
    const abort = new DOMException('Aborted', 'AbortError');
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(abort)),
    );
    await expect(get('/health', controller.signal)).rejects.toBe(abort);
  });

  it('throws instead of returning null when a 2xx is not JSON', async () => {
    answer(200, '<!doctype html><title>CandleStack</title>', { 'Content-Type': 'text/html' });
    const error = await errorOf(get('/health'));
    expect(error.status).toBe(200);
    expect(error.message).toMatch(/cannot read/);
  });
});

describe('parseRetryAfter', () => {
  const now = Date.parse('2026-10-08T12:00:00Z');

  it('reads whole seconds, including 0', () => {
    expect(parseRetryAfter('30', now)).toBe(30);
    expect(parseRetryAfter('0', now)).toBe(0);
    expect(parseRetryAfter(' 5 ', now)).toBe(5);
  });

  it('reads an HTTP date as the seconds until it, never below 0', () => {
    expect(parseRetryAfter('Thu, 08 Oct 2026 12:00:42 GMT', now)).toBe(42);
    expect(parseRetryAfter('Thu, 08 Oct 2026 11:59:00 GMT', now)).toBe(0);
  });

  it('treats a missing or malformed value as no hint', () => {
    expect(parseRetryAfter(null, now)).toBeUndefined();
    expect(parseRetryAfter('', now)).toBeUndefined();
    expect(parseRetryAfter('soon', now)).toBeUndefined();
    expect(parseRetryAfter('-5', now)).toBeUndefined();
    expect(parseRetryAfter('1.5', now)).toBeUndefined();
  });
});

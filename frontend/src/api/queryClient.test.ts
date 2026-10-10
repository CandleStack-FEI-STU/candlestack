import { describe, expect, it } from 'vitest';

import { ApiError } from './client';
import { shouldRetry } from './queryClient';

describe('shouldRetry', () => {
  it('retries once on no answer and on gateway errors', () => {
    for (const status of [0, 502, 504]) {
      expect(shouldRetry(0, new ApiError(status, 'x'))).toBe(true);
      expect(shouldRetry(1, new ApiError(status, 'x'))).toBe(false);
    }
  });

  it('never retries when the server says how long to wait', () => {
    expect(shouldRetry(0, new ApiError(503, 'x', { retryAfter: 1 }))).toBe(false);
    expect(shouldRetry(0, new ApiError(429, 'x', { retryAfter: 0 }))).toBe(false);
    expect(shouldRetry(0, new ApiError(502, 'x', { retryAfter: 5 }))).toBe(false);
  });

  it('never retries other answers or errors that are not from the API', () => {
    for (const status of [400, 404, 422, 429, 500, 503]) {
      expect(shouldRetry(0, new ApiError(status, 'x'))).toBe(false);
    }
    expect(shouldRetry(0, new TypeError('bug'))).toBe(false);
  });
});

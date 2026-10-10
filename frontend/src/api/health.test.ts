import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from './client';
import { getHealth } from './health';

const report = { status: 'error', env: 'prod', version: '0.4.0', commit: 'abc', redis: 'error' };

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('getHealth', () => {
  it('returns the 503 body when it is a health report (Redis down)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(new Response(JSON.stringify(report), { status: 503 }))),
    );
    await expect(getHealth()).resolves.toEqual(report);
  });

  it('throws on a 503 whose body is not a health report', async () => {
    const problem = { type: 'https://candlestack.tech/problems/source-unavailable', status: 503, detail: 'Down.' };
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(new Response(JSON.stringify(problem), { status: 503 }))),
    );
    await expect(getHealth()).rejects.toBeInstanceOf(ApiError);
  });
});

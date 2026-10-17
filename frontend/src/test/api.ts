import { vi } from 'vitest';

import type { Me } from '@/api';

// A signed-in user as GET /api/v1/me sends it.
export const ARSEN: Me = {
  id: 'usr_7f3k2m9qx4',
  display_name: 'Arsen Labovich',
  email: 'arsen@example.com',
  providers: ['github'],
  created_at: '2026-10-17T08:00:00Z',
};

type Answer = { status: number; body?: unknown };

// The API's answer when this browser has no session.
export const NOT_SIGNED_IN: Answer = {
  status: 401,
  body: {
    type: 'https://candlestack.tech/problems/not-signed-in',
    title: 'Not signed in',
    status: 401,
    detail: 'Sign in to use this.',
  },
};

// Stubs fetch with the given answers, by method and path ("GET /api/v1/me", as src/api/client.ts
// calls it); anything else is a 404. Returns the stub, to check what was asked.
export function stubApi(answers: Record<string, Answer>) {
  const fetch = vi.fn((path: string, init?: RequestInit) => {
    const answer = answers[`${init?.method ?? 'GET'} ${path}`] ?? {
      status: 404,
      body: { title: 'Not found' },
    };
    const body = answer.body === undefined ? null : JSON.stringify(answer.body);
    return Promise.resolve(new Response(body, { status: answer.status }));
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

// The answers of a session: GET /api/v1/me gives the user, or 401 without one.
export const session = (user: Me | null): Record<string, Answer> => ({
  'GET /api/v1/me': user === null ? NOT_SIGNED_IN : { status: 200, body: user },
});

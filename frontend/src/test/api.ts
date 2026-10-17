import { vi } from 'vitest';

import type { Me, Preferences } from '@/api';

// A signed-in user as GET /api/v1/me sends it.
export const ARSEN: Me = {
  id: 'usr_7f3k2m9qx4',
  display_name: 'Arsen Labovich',
  email: 'arsen@example.com',
  providers: ['github'],
  sign_in_methods: [{ provider: 'github', email: 'arsen@example.com', login: 'arsen' }],
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

// GET /api/v1/me/preferences of a user who never changed a setting: the API's defaults.
export const DEFAULT_PREFERENCES: Preferences = {
  backtest_defaults: {
    timeframe: '30m',
    period_start: '2021-01-04',
    period_end: '2024-12-31',
    direction: 'long',
    threshold: 0.05,
    stop_loss_pct: 7,
    fees_pct: 0.1,
    slippage_pct: 0.02,
    benchmark: 'bh',
  },
  appearance: { theme: 'dark', time_zone: 'ny', date_format: 'dmy', time_format: '24', reduce_motion: false },
};

// The answers of a session with its preferences.
export const sessionWithPreferences = (user: Me, preferences: Preferences = DEFAULT_PREFERENCES) => ({
  ...session(user),
  'GET /api/v1/me/preferences': { status: 200, body: preferences },
});

// The JSON body of the request the stub got for `method path`, the last one if there were several.
export function sentBody(fetch: ReturnType<typeof stubApi>, request: string): unknown {
  const [method, path] = request.split(' ');
  const call = fetch.mock.calls.findLast(([url, init]) => url === path && (init?.method ?? 'GET') === method);
  const body = call?.[1]?.body;
  return typeof body === 'string' ? JSON.parse(body) : undefined;
}

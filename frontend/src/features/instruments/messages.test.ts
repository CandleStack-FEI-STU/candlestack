import { describe, expect, it } from 'vitest';

import { ApiError } from '@/api';

import { describeListError, emptyMessage, unavailableMessage } from './messages';

describe('messages', () => {
  it('names the query and the market when nothing matches', () => {
    expect(emptyMessage('zzz', undefined)).toMatch(/No instruments match “zzz”\./);
    expect(emptyMessage('zzz', 'stock')).toMatch(/“zzz” in stocks\./);
    expect(emptyMessage('', 'crypto')).toBe('No instruments in crypto pairs.');
  });

  it('says which market is left out', () => {
    expect(unavailableMessage([])).toBeUndefined();
    expect(unavailableMessage(['stock'])).toMatch(/^Stocks cannot be searched right now/);
  });

  it('explains the old API that cannot list without a query, where retrying does not help', () => {
    const old = new ApiError(422, "query parameter 'q': Field required");
    expect(describeListError(old, '')).toEqual({
      title: 'This server cannot show the whole list yet.',
      hint: expect.stringMatching(/older version of the API that only searches\. Type a symbol/),
      canRetry: false,
      tone: 'warn',
      detail: "Server: query parameter 'q': Field required (HTTP 422)",
    });
    expect(describeListError(old, 'btc').title).toBe('The server did not accept this search.');
  });

  it('says how long to wait when the source is down', () => {
    const down = describeListError(new ApiError(503, 'Alpaca is down.', { retryAfter: 30 }), 'apple');
    expect(down.title).toBe('The instrument catalog is unavailable right now.');
    expect(down.hint).toBe('The data source did not answer. Try again in 30 s.');
    expect(down.canRetry).toBe(true);
    expect(describeListError(new ApiError(500, 'Boom.'), '').title).toBe('The server ran into a problem.');
  });

  it('tells a lost connection from a bug in the app', () => {
    const offline = describeListError(new ApiError(0, 'Cannot reach the server. Check your connection.'), '');
    expect(offline.title).toBe('No connection to the CandleStack server.');
    expect(offline.detail).toBeUndefined();
    const bug = describeListError(new TypeError('x is undefined'), '');
    expect(bug.title).toBe('Something went wrong in the app.');
    expect(bug.detail).toBe('x is undefined');
  });
});

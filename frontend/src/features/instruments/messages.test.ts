import { describe, expect, it } from 'vitest';

import { ApiError } from '@/api';

import { emptyMessage, errorMessage, unavailableMessage } from './messages';

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

  it('shows the API detail and how long to wait', () => {
    const limited = new ApiError(503, 'Alpaca is down.', { retryAfter: 30 });
    expect(errorMessage(limited)).toBe('The instrument list could not be loaded: Alpaca is down. Try again in 30 s.');
    expect(errorMessage(new ApiError(0, 'Cannot reach the server. Check your connection.'))).toBe(
      'Cannot reach the server. Check your connection.',
    );
    expect(errorMessage(new TypeError('x'))).toBe('Something went wrong. Reload the page.');
  });
});

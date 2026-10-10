import { describe, expect, it } from 'vitest';

import { MAX_AUTO_RETRIES, shouldAutoRetry } from './retries';

describe('automatic retries of the candles', () => {
  it('retry when the server says how long to wait, a few times in a row', () => {
    expect(shouldAutoRetry(30, 0)).toBe(true);
    expect(shouldAutoRetry(30, MAX_AUTO_RETRIES - 1)).toBe(true);
  });

  it('stop after MAX_AUTO_RETRIES and leave it to the user', () => {
    expect(shouldAutoRetry(30, MAX_AUTO_RETRIES)).toBe(false);
  });

  it('never retry on their own without Retry-After', () => {
    expect(shouldAutoRetry(undefined, 0)).toBe(false);
  });
});

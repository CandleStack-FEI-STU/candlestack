import { describe, expect, it } from 'vitest';

import { MAX_AUTO_RETRIES, countdownStep, shouldAutoRetry } from './retries';

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

describe('the Retry-After countdown', () => {
  it('counts down and retries once, on the last second', () => {
    expect(countdownStep(3)).toEqual({ next: 2, fire: false });
    expect(countdownStep(2)).toEqual({ next: 1, fire: false });
    expect(countdownStep(1)).toEqual({ next: 0, fire: true });
  });

  it('does not retry again once it is at 0', () => {
    expect(countdownStep(0)).toEqual({ next: 0, fire: false });
  });
});

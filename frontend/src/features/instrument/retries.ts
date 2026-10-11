// How many times in a row the candles retry on their own before the user decides: a source that
// stays down for long should not be asked every Retry-After seconds forever.
export const MAX_AUTO_RETRIES = 3;

// Retry on its own when the server said how long to wait and the retries are not used up.
export function shouldAutoRetry(wait: number | undefined, autoRetries: number): wait is number {
  return wait !== undefined && autoRetries < MAX_AUTO_RETRIES;
}

// One second of the Retry-After countdown: the seconds left after it, and whether that second
// was the last one, when the retry goes out.
export function countdownStep(left: number): { next: number; fire: boolean } {
  const next = Math.max(left - 1, 0);
  return { next, fire: left > 0 && next === 0 };
}

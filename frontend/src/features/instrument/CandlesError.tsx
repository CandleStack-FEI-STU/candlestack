import { useEffect, useRef, useState } from 'react';

import { ApiError } from '@/api';
import { Button } from '@/components/ui/button';

import { countdownStep, shouldAutoRetry } from './retries';

// Counts Retry-After down once a second and retries when it reaches 0. The retry happens in the
// timer's callback, not in the effect: StrictMode runs effects twice in dev, but a timer that
// the first run set up is cleared before it fires, so the retry is counted once.
function useCountdown(seconds: number, onDone: () => void): number {
  const [left, setLeft] = useState(() => Math.max(seconds, 1));
  const done = useRef(onDone);
  useEffect(() => {
    done.current = onDone;
  }, [onDone]);
  useEffect(() => {
    if (left <= 0) return;
    const timer = setTimeout(() => {
      const step = countdownStep(left);
      if (step.fire) done.current();
      setLeft(step.next);
    }, 1000);
    return () => clearTimeout(timer);
  }, [left]);
  return left;
}

function Countdown({ seconds, message, onRetry }: { seconds: number; message: string; onRetry: () => void }) {
  const left = useCountdown(seconds, onRetry);
  return (
    <output>
      {message} Try again in {left} s.
    </output>
  );
}

type Props = { error: Error; errorAt: number; autoRetries: number; onRetry: () => void; onAutoRetry: () => void };

// An error of the candle requests. When the server says how long to wait (429, 503), the page
// waits that long and asks again itself, a few times in a row (see retries.ts); otherwise, and
// after that, the user decides.
export function CandlesError({ error, errorAt, autoRetries, onRetry, onAutoRetry }: Props) {
  const wait = error instanceof ApiError ? error.retryAfter : undefined;
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-md border border-destructive/40 px-4 py-3 text-sm">
      {shouldAutoRetry(wait, autoRetries) ? (
        <Countdown key={errorAt} seconds={wait} message={error.message} onRetry={onAutoRetry} />
      ) : (
        <>
          <p role="alert">{error.message}</p>
          <Button variant="outline" size="sm" onClick={onRetry}>
            Try again
          </Button>
        </>
      )}
    </div>
  );
}

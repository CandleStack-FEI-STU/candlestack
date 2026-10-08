import { useEffect, useRef, useState } from 'react';

import { ApiError } from '@/api';
import { Button } from '@/components/ui/button';

// Counts Retry-After down once a second; reaching 0 retries on its own, once.
function useCountdown(seconds: number, onDone: () => void): number {
  const [left, setLeft] = useState(seconds);
  const done = useRef(onDone);
  useEffect(() => {
    done.current = onDone;
  }, [onDone]);
  useEffect(() => {
    if (left <= 0) {
      done.current();
      return;
    }
    const timer = setTimeout(() => setLeft(left - 1), 1000);
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

// An error of the candle requests. When the server says how long to wait (429, 503), the page
// waits that long and asks again itself; otherwise the user decides.
export function CandlesError({ error, errorAt, onRetry }: { error: Error; errorAt: number; onRetry: () => void }) {
  const wait = error instanceof ApiError ? error.retryAfter : undefined;
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-md border border-destructive/40 px-4 py-3 text-sm">
      {wait === undefined ? (
        <>
          <p role="alert">{error.message}</p>
          <Button variant="outline" size="sm" onClick={onRetry}>
            Try again
          </Button>
        </>
      ) : (
        <Countdown key={errorAt} seconds={wait} message={error.message} onRetry={onRetry} />
      )}
    </div>
  );
}

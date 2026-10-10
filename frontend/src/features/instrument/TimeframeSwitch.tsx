import { Link } from '@tanstack/react-router';

import type { Timeframe } from '@/api';
import { cn } from '@/lib/utils';

// Links, not buttons: the timeframe lives in the URL (?tf=1h), so the address opens the same view.
export function TimeframeSwitch({ timeframes, current }: { timeframes: readonly Timeframe[]; current: Timeframe }) {
  return (
    <nav aria-label="Timeframe" className="flex flex-wrap gap-1">
      {timeframes.map((tf) => (
        <Link
          key={tf}
          from="/instrument/$id"
          search={{ tf }}
          replace
          aria-current={tf === current ? 'page' : undefined}
          className={cn(
            'rounded-md border px-3 py-1 font-mono text-sm text-muted-foreground transition-colors hover:text-foreground',
            tf === current && 'border-primary text-primary hover:text-primary',
          )}
        >
          {tf}
        </Link>
      ))}
    </nav>
  );
}

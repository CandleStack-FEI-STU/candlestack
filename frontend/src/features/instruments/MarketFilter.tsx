import { Link } from '@tanstack/react-router';

import type { Market } from '@/api';
import { cn } from '@/lib/utils';

const OPTIONS: { label: string; market: Market | undefined }[] = [
  { label: 'All', market: undefined },
  { label: 'Stocks', market: 'stock' },
  { label: 'Crypto', market: 'crypto' },
];

// Links, like the timeframe switch: the market is part of the URL. A new market starts at page 1.
export function MarketFilter({ current }: { current: Market | undefined }) {
  return (
    <nav aria-label="Market" className="flex gap-1">
      {OPTIONS.map(({ label, market }) => (
        <Link
          key={label}
          from="/"
          search={(prev) => ({
            q: 'q' in prev ? prev.q : undefined,
            market,
            // Crypto pairs have no exchange: switching to them drops it.
            exchange: market !== 'crypto' && 'exchange' in prev ? prev.exchange : undefined,
          })}
          replace
          aria-current={market === current ? 'page' : undefined}
          className={cn(
            'rounded-md border px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground',
            market === current && 'border-primary text-primary hover:text-primary',
          )}
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}

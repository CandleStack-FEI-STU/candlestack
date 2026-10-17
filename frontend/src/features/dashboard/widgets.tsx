import { Link } from '@tanstack/react-router';
import type { ReactNode } from 'react';

import type { Backtest } from '@/api';
import { sparkPaths } from './sparkline';

// The parts the dashboard's widgets share (mockups/app, ddDash).

// The muted 12 px hint at a widget's right ("by Sharpe") or as its only line.
export function Hint({ children }: { children: ReactNode }) {
  return <span className="text-xs text-muted-foreground">{children}</span>;
}

// The accent link at a widget's right (.link): "All backtests".
export function WidgetLink({ to, children }: { to: '/backtests'; children: string }) {
  return (
    <Link
      to={to}
      className="text-[13px] font-medium text-primary underline-offset-2 transition-colors duration-150 outline-none hover:underline focus-visible:underline motion-reduce:transition-none"
    >
      {children}
    </Link>
  );
}

// Starred widgets show their best four; with more, the row under a line leads to all of them
// (.dd-more): "More … 5 starred →".
export const TOP = 4;

export function MoreRow({ total, to }: { total: number; to: '/backtests' | '/models' }) {
  if (total <= TOP) return null;
  return (
    <Link
      to={to}
      className="mt-1.5 flex w-full justify-between gap-2.5 border-t px-1.5 pt-2.5 text-[12.5px] font-medium text-muted-foreground transition-colors duration-150 outline-none hover:text-foreground focus-visible:text-foreground motion-reduce:transition-none"
    >
      <span>More</span>
      <span>{total} starred →</span>
    </Link>
  );
}

// A row of a starred list (.dd-sr): the whole row lights up on hover and opens what it stands for.
export const STARRED_ROW =
  'relative grid w-full items-center gap-2.5 rounded-md px-1.5 py-2 text-left transition-colors duration-150 hover:bg-muted motion-reduce:transition-none';

// A small equity line, 52 × 20 px (mockups/app, spark): the strategy in the accent, buy and hold
// dashed and muted.
export function Sparkline({ equity }: { equity: NonNullable<Backtest['equity']> }) {
  const paths = sparkPaths(equity.strategy, equity.benchmark, 52, 20);
  return (
    <svg viewBox="0 0 52 20" aria-hidden="true" className="h-5 w-[52px] flex-none">
      <path d={paths.benchmark} strokeDasharray="5 4" className="fill-none stroke-muted-foreground stroke-[1.5]" />
      <path d={paths.strategy} className="fill-none stroke-primary stroke-2" />
    </svg>
  );
}

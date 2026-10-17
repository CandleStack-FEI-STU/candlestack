import type { ReactNode } from 'react';

import { cn } from '@/lib/utils';

// The app design's hint (mockups/app, .hint): 12 px on an 18 px line (1.5), muted. Tailwind's
// text-xs would give a 16 px line. Every hint of the signed-in app is written with it.
export const HINT = 'text-[12px]/[1.5] text-muted-foreground';

export function Hint({ className, children }: { className?: string; children: ReactNode }) {
  return <span className={cn(HINT, className)}>{children}</span>;
}

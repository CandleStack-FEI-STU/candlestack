import type { ReactNode } from 'react';

import { cn } from '@/lib/utils';

// .hint: 12 px on an 18 px line (1.5), muted. Tailwind's text-xs would give 16 px.
export const HINT = 'text-[12px]/[1.5] text-muted-foreground';

// What went wrong, in the design's hint style (.hint: 12 px, muted), the one it has for a line of
// text in a card (Settings, the dashboard's widgets). Read out as soon as it shows.
export function ErrorNote({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <p role="alert" className={cn(HINT, className)}>
      {children}
    </p>
  );
}

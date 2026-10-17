import type { ReactNode } from 'react';

import { HINT } from '@/components/Hint';
import { cn } from '@/lib/utils';

// What went wrong, in the design's hint style, the one it has for a line of text in a card
// (Settings, the dashboard's widgets). Read out as soon as it shows.
export function ErrorNote({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <p role="alert" className={cn(HINT, className)}>
      {children}
    </p>
  );
}

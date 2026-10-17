import type { ReactNode } from 'react';

// The small uppercase label above a heading, a pipeline step or the sidebar's storage.
export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <span className="font-mono text-[11px]/4 font-medium tracking-[0.06em] text-muted-foreground uppercase">
      {children}
    </span>
  );
}

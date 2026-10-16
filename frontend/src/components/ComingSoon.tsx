import type { ReactNode } from 'react';

import { AccentDot } from '@/components/AccentDot';
import { cn } from '@/lib/utils';

// A grey bar of a sketch, `width` percent of its cell. Faint: a heading or a second line. A tone
// tints a return.
const TONES = {
  up: 'bg-[color-mix(in_srgb,var(--up)_26%,var(--bg))]',
  down: 'bg-[color-mix(in_srgb,var(--down)_24%,var(--bg))]',
};

type BarProps = { width: number; faint?: boolean; tone?: keyof typeof TONES | undefined };

export function Bar({ width, faint = false, tone }: BarProps) {
  const fill = tone ? TONES[tone] : faint ? 'bg-muted' : 'bg-[color-mix(in_srgb,var(--ink)_9%,var(--bg))]';
  return (
    <span className={cn('block rounded-[5px]', faint ? 'h-[7px]' : 'h-[9px]', fill)} style={{ width: `${width}%` }} />
  );
}

// A part that is not built yet: a faint sketch of what will be there, fading out downwards, and
// the tag over it. Screen readers only hear the tag. On the home page and in the app's Coming
// soon dialogs.
export function ComingSoon({ children }: { children: ReactNode }) {
  return (
    <div className="relative overflow-hidden rounded-xl border bg-card p-5">
      <div aria-hidden className="[mask-image:linear-gradient(180deg,#000_20%,transparent_105%)]">
        {children}
      </div>
      <span className="absolute top-1/2 left-1/2 inline-flex -translate-1/2 items-center gap-[9px] rounded-full border bg-card px-4 py-2 font-mono text-[12.5px]/[normal] font-medium tracking-[0.07em] whitespace-nowrap text-foreground uppercase shadow-[0_8px_24px_rgb(0_0_0/0.08)] dark:shadow-[0_8px_24px_rgb(0_0_0/0.5)]">
        <AccentDot />
        Coming soon
      </span>
    </div>
  );
}

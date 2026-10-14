import type { ReactNode } from 'react';

import { cn } from '@/lib/utils';

// The small uppercase label above a heading or a pipeline step.
export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <span className="font-mono text-[11px]/4 font-medium tracking-[0.06em] text-muted-foreground uppercase">
      {children}
    </span>
  );
}

type SectionProps = { id: string; split?: boolean; children: ReactNode };

// A section under the hero, below a hairline. Split: the text on the left and its example on the
// right, one over the other up to 980 px like in the design.
export function Section({ id, split = false, children }: SectionProps) {
  return (
    <section
      id={id}
      className={cn(
        'border-t py-9',
        split &&
          'grid grid-cols-[minmax(0,1fr)] items-start gap-8 min-[981px]:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]',
      )}
    >
      {children}
    </section>
  );
}

type IntroProps = { eyebrow: string; title: string; text: string };

// A section's label, heading and one or two sentences under it.
export function SectionIntro({ eyebrow, title, text }: IntroProps) {
  return (
    <>
      <Eyebrow>{eyebrow}</Eyebrow>
      <h2 className="mt-1.5 text-[22px] font-bold tracking-[-0.02em] text-balance">{title}</h2>
      <p className="mt-1.5 max-w-[62ch] text-muted-foreground">{text}</p>
    </>
  );
}

import { useId, type ComponentType, type ReactNode, type SVGProps } from 'react';

import { cn } from '@/lib/utils';

// The parts every section of Settings is built of (mockups/app, ddSettings): a card in the
// dashboard's style with an icon by its title, rows of a label and a control, and a footer.

type CardProps = {
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  title: string;
  // At the right of the title: a hint or the Coming soon tag.
  aside?: ReactNode;
  // The account's card: a red rim and a red icon.
  danger?: boolean;
  children: ReactNode;
};

// 16 px inside (12 px on a phone), the parts 4 px apart. The title row: a 26 px tile with the
// 15 px icon, the 16 px title, 10 px above the rest.
export function SettingsCard({ icon: Icon, title, aside, danger = false, children }: CardProps) {
  const id = useId();
  return (
    <section
      aria-labelledby={id}
      className={cn(
        'flex min-w-0 flex-col gap-1 rounded-lg border bg-card p-4 max-[640px]:p-3',
        danger && 'border-[color-mix(in_srgb,var(--down)_30%,var(--rule))]',
      )}
    >
      <div data-slot="settings-head" className="mb-2.5 flex flex-wrap items-baseline justify-between gap-2.5">
        <div className="flex items-center gap-2.5">
          <span
            className={cn(
              'grid size-[26px] flex-none place-items-center rounded-[7px]',
              danger
                ? 'bg-[color-mix(in_srgb,var(--down)_12%,var(--bg))] text-down'
                : 'bg-[color-mix(in_srgb,var(--accent)_12%,var(--bg))] text-primary',
            )}
          >
            <Icon className="size-[15px]" />
          </span>
          <h2 id={id} className="text-base font-semibold">
            {title}
          </h2>
        </div>
        {aside}
      </div>
      {children}
    </section>
  );
}

// A row's top line, except right under the title.
const RULED = 'border-t [[data-slot=settings-head]+&]:border-t-0';

type RowProps = { label: string; hint?: ReactNode; top?: boolean; children: ReactNode };

// A 128 px label (13.5 px, its hint 11.5 px under it), 12 px, then the control. `top` lines the
// label up with the top of a tall control instead of its middle.
export function SettingsRow({ label, hint, top = false, children }: RowProps) {
  return (
    <div
      className={cn('grid grid-cols-[128px_minmax(0,1fr)] gap-3 py-[9px]', top ? 'items-start' : 'items-center', RULED)}
    >
      <span className="flex flex-col text-[13.5px]">
        {label}
        {hint && <span className="text-[11.5px] text-muted-foreground">{hint}</span>}
      </span>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

// A line under the title saying what the card is for.
export function SettingsLead({ children }: { children: ReactNode }) {
  return <p className="-mt-1 mb-2 text-xs text-muted-foreground">{children}</p>;
}

// An action of the account card: what it does over a hint, its button at the right.
export function ActionRow({ title, hint, children }: { title: string; hint: string; children: ReactNode }) {
  return (
    <div className={cn('flex items-center justify-between gap-3 py-2.5', RULED)}>
      <div className="flex flex-col gap-0.5">
        <b>{title}</b>
        <span className="text-xs text-muted-foreground">{hint}</span>
      </div>
      {children}
    </div>
  );
}

// The card's button at the right under a line; a failure to save says so at the left.
export function SettingsFooter({ error, children }: { error?: string | undefined; children: ReactNode }) {
  return (
    <div className="flex items-center justify-end gap-3 border-t pt-2.5">
      {error && <ErrorNote className="mr-auto">{error}</ErrorNote>}
      {children}
    </div>
  );
}

// What went wrong, in the size of a hint and in red. Read out as soon as it shows.
export function ErrorNote({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <p role="alert" className={cn('text-xs text-down', className)}>
      {children}
    </p>
  );
}

// .inp in a card: 34 px, the text in the app's sans, at most 260 px wide.
export const INPUT =
  'h-[34px] w-full max-w-[260px] min-w-0 rounded-md border bg-background px-2.5 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 aria-invalid:border-down';

// .st-id code: an id in mono on the surface.
export function Code({ children }: { children: ReactNode }) {
  return <code className="rounded-[5px] bg-muted px-2 py-[3px] font-mono text-[13px]">{children}</code>;
}

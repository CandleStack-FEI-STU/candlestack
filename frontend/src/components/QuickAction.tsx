import type { ComponentProps, ComponentType, ReactNode, SVGProps } from 'react';

import { cn } from '@/lib/utils';

type Icon = ComponentType<SVGProps<SVGSVGElement>>;

// An icon on a 36 px tile (.qa-i): ink on the stronger surface, or white on the accent for the
// first action.
export function QuickActionTile({ icon: Icon, primary = false }: { icon: Icon; primary?: boolean }) {
  return (
    <span
      className={cn(
        'grid size-9 flex-none place-items-center rounded-[9px]',
        primary ? 'bg-primary text-primary-foreground' : 'bg-surface-2 text-foreground',
      )}
    >
      <Icon className="size-[18px]" />
    </span>
  );
}

type Props = ComponentProps<'button'> & {
  icon: Icon;
  title: string;
  // The line under the title: a hint, or the frameworks' marks.
  line: ReactNode;
  // The first action (.qa-c.pri): on the accent's tint, which stays on hover.
  primary?: boolean;
};

// A quick action of the dashboard and the Models page (mockups/app, .qa-c): the icon tile, the
// title and a line under it. It rises 1 px with a shadow on hover. A button, so a dialog's trigger
// can pass its props on.
export function QuickAction({ icon, title, line, primary = false, className, ...props }: Props) {
  return (
    <button
      type="button"
      className={cn(
        'flex min-w-0 cursor-pointer items-center gap-3 rounded-[10px] border px-4 py-3.5 text-left transition-[background-color,border-color,box-shadow,translate] duration-150 outline-none hover:-translate-y-px hover:shadow-[0_4px_14px_var(--shadow)] focus-visible:ring-[3px] focus-visible:ring-ring/50 motion-reduce:transition-none',
        primary
          ? 'border-[color-mix(in_srgb,var(--accent)_40%,var(--rule))] bg-accent-soft'
          : 'bg-card hover:border-[color-mix(in_srgb,var(--accent)_45%,var(--rule))] hover:bg-muted',
        className,
      )}
      {...props}
    >
      <QuickActionTile icon={icon} primary={primary} />
      <span className="flex min-w-0 flex-col gap-[3px]">
        <b className="font-semibold">{title}</b>
        {line}
      </span>
    </button>
  );
}

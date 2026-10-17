import { useId, type ComponentType, type ReactNode, type SVGProps } from 'react';

import { cn } from '@/lib/utils';

type Props = {
  // Without one, the title stands alone (the dashboard's Get started).
  icon?: ComponentType<SVGProps<SVGSVGElement>>;
  title: string;
  // At the right of the title: a hint, a link or the Coming soon tag.
  aside?: ReactNode;
  // A card about something that cannot be undone: a red rim and a red icon.
  danger?: boolean;
  // The parts' spacing where it differs: the dashboard's widgets have none between them.
  className?: string;
  children: ReactNode;
};

// A card in the dashboard's style (mockups/app, .dd-card with .dd-h and .dd-ic), as Settings and
// the dashboard use it: 16 px inside (12 px on a phone), the parts 4 px apart. The title row: a
// 26 px tile with the 15 px icon, the 16 px title, 10 px above the rest. The head is marked
// `data-slot="card-head"`, so the first row under it can drop its top line.
export function DashboardCard({ icon: Icon, title, aside, danger = false, className, children }: Props) {
  const id = useId();
  return (
    <section
      aria-labelledby={id}
      className={cn(
        'flex min-w-0 flex-col gap-1 rounded-lg border bg-card p-4 max-[640px]:p-3',
        danger && 'border-[color-mix(in_srgb,var(--down)_30%,var(--rule))]',
        className,
      )}
    >
      <div data-slot="card-head" className="mb-2.5 flex flex-wrap items-baseline justify-between gap-2.5">
        <div className="flex items-center gap-2.5">
          {Icon && (
            <span
              className={cn(
                'grid size-[26px] flex-none place-items-center rounded-[7px]',
                danger ? 'bg-down-soft text-down' : 'bg-accent-soft text-primary',
              )}
            >
              <Icon className="size-[15px]" />
            </span>
          )}
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

import { Link } from '@tanstack/react-router';
import { LayoutGrid } from 'lucide-react';

import { BacktestsIcon, ModelsIcon, SettingsIcon } from '@/components/icons';

const SECTIONS = [
  { to: '/dashboard', label: 'Dashboard', Icon: LayoutGrid },
  { to: '/backtests', label: 'Backtests', Icon: BacktestsIcon },
  { to: '/models', label: 'Models', Icon: ModelsIcon },
  { to: '/settings', label: 'Settings', Icon: SettingsIcon },
] as const;

// Muted, ink on hover with a surface behind it; the open section ink and medium on a darker
// surface (the link marks it with data-status and aria-current). Hovering it changes nothing.
const ITEM =
  'flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 whitespace-nowrap text-muted-foreground transition-colors duration-150 hover:text-foreground hover:not-data-[status=active]:bg-muted data-[status=active]:bg-[color-mix(in_srgb,var(--ink)_9%,var(--bg))] data-[status=active]:font-medium data-[status=active]:text-foreground motion-reduce:transition-none max-[980px]:w-auto max-[980px]:flex-none';

// The workspace's sections beside the page (mockups/app, direction D): a 200 px card. Up to 980 px
// wide it lies above the page as a row that scrolls sideways.
export function Sidebar() {
  return (
    <nav
      aria-label="Workspace"
      className="flex flex-col gap-0.5 rounded-lg border bg-card p-2 max-[980px]:flex-row max-[980px]:overflow-x-auto max-[980px]:p-1"
    >
      {SECTIONS.map(({ to, label, Icon }) => (
        <Link key={to} to={to} className={ITEM}>
          <Icon className="size-4 shrink-0" />
          {label}
        </Link>
      ))}
    </nav>
  );
}

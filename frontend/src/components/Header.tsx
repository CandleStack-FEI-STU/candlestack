import { Link, useRouterState } from '@tanstack/react-router';

import { Logo } from '@/brand/Logo';
import { ApiStatus } from '@/components/ApiStatus';
import { ThemeToggle } from '@/components/ThemeToggle';
import { QuickSearch } from '@/features/instruments';

// The list page has its own search box; every other page gets one in the header.
export function Header() {
  const onList = useRouterState({ select: (state) => state.location.pathname === '/' });
  return (
    <header className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur">
      {/* Relative: on a phone the quick search's list hangs from this bar, the full width of the
          screen, not from its narrow search box (QuickSearch.tsx). */}
      <div className="relative mx-auto flex h-14 max-w-[96rem] items-center justify-between px-4 lg:px-8">
        <Link to="/" aria-label="CandleStack home" className="shrink-0 rounded-md">
          <Logo />
        </Link>
        {/* Narrower gaps on a phone leave the search box room for its placeholder. */}
        <div className="flex min-w-0 flex-1 items-center justify-end gap-2 pl-3 sm:gap-3 sm:pl-4">
          {!onList && <QuickSearch />}
          <ApiStatus />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

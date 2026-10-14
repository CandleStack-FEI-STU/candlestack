import { Link, useRouterState } from '@tanstack/react-router';

import { Logo } from '@/brand/Logo';
import { ThemeToggle } from '@/components/ThemeToggle';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

type Section = 'product' | 'instruments';

// The nav item a page belongs to: an instrument is part of Instruments, though not the list itself.
function sectionOf(pathname: string): Section | undefined {
  if (pathname === '/') return 'product';
  if (pathname === '/instruments' || pathname.startsWith('/instrument/')) return 'instruments';
  return undefined;
}

const NAV = 'text-muted-foreground hover:text-foreground';
const ON = 'font-medium text-foreground';
// The mockup's 34 px buttons (design repository, mockups/home), each with a 1 px border.
const BUTTON = 'h-[34px] border border-transparent px-3.5';

// No room on a phone: the logo leads home and the list is a link on the home page.
function MainNav() {
  const section = useRouterState({ select: (state) => sectionOf(state.location.pathname) });
  return (
    <nav aria-label="Main" className="flex gap-[18px] text-sm max-sm:hidden">
      <Link to="/" className={cn(NAV, section === 'product' && ON)}>
        Product
      </Link>
      <Link
        to="/instruments"
        activeOptions={{ includeSearch: false }}
        className={cn(NAV, section === 'instruments' && ON)}
      >
        Instruments
      </Link>
      {/* Same origin, so stage links to the stage API. */}
      <a href="/api/v1/docs" target="_blank" rel="noopener" className={NAV}>
        API
      </a>
    </nav>
  );
}

// No action yet: the backtest builder and accounts are not designed. Sign in waits for md: with
// the nav, the row needs about 675 px.
function Actions() {
  return (
    <div className="ml-auto flex items-center gap-2">
      <Button type="button" variant="ghost" className={cn(BUTTON, 'max-md:hidden')}>
        Sign in
      </Button>
      <Button
        type="button"
        className={cn(BUTTON, 'border-primary shadow-none hover:bg-[color-mix(in_srgb,var(--accent)_86%,var(--ink))]')}
      >
        Try Backtest
      </Button>
      <ThemeToggle />
    </div>
  );
}

// Sticky on top of every page, a little see-through, blurring what scrolls under it. z-30: above
// the list's mini candles and the chart's legend (z-10, z-20), which would otherwise scroll over
// it. The safe-area insets keep it clear of a notch once the page is drawn under one.
export function Header() {
  return (
    <header className="sticky top-[env(safe-area-inset-top,0px)] z-30 border-b bg-background/88 pr-[max(24px,env(safe-area-inset-right,0px))] pl-[max(24px,env(safe-area-inset-left,0px))] backdrop-blur-sm max-sm:pr-[max(12px,env(safe-area-inset-right,0px))] max-sm:pl-[max(12px,env(safe-area-inset-left,0px))]">
      <div className="mx-auto flex h-14 max-w-[72rem] items-center gap-5 max-sm:gap-2.5">
        <Link to="/" aria-label="CandleStack home" className="shrink-0 rounded-md leading-[0]">
          <Logo className="max-sm:h-6" />
        </Link>
        <MainNav />
        <Actions />
      </div>
    </header>
  );
}

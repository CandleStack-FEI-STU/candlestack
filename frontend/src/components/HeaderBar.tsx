import { Link } from '@tanstack/react-router';
import type { ReactNode } from 'react';

import { Logo } from '@/brand/Logo';

type Props = { home: '/' | '/dashboard'; homeLabel: string; children: ReactNode };

// The bar on top of both layouts: the logo, leading to the layout's start page, then the layout's
// own nav and buttons. Sticky, a little see-through, blurring what scrolls under it. z-30: above
// the list's mini candles and the chart's legend (z-10, z-20), which would otherwise scroll over
// it. The safe-area insets keep it clear of a notch once the page is drawn under one.
export function HeaderBar({ home, homeLabel, children }: Props) {
  return (
    <header className="sticky top-[env(safe-area-inset-top,0px)] z-30 border-b bg-background/88 pr-[max(24px,env(safe-area-inset-right,0px))] pl-[max(24px,env(safe-area-inset-left,0px))] backdrop-blur-sm max-sm:pr-[max(12px,env(safe-area-inset-right,0px))] max-sm:pl-[max(12px,env(safe-area-inset-left,0px))]">
      <div className="mx-auto flex h-14 max-w-[72rem] items-center gap-5 max-sm:gap-2.5">
        <Link to={home} aria-label={homeLabel} className="shrink-0 rounded-md leading-[0]">
          <Logo className="max-sm:h-6" />
        </Link>
        {children}
      </div>
    </header>
  );
}

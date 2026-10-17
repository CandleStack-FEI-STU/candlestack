import { Outlet } from '@tanstack/react-router';
import type { ReactNode } from 'react';

import { Footer } from '@/components/Footer';
import { Header } from '@/components/Header';

// Every page: a header on top, the page itself in a centered column below, the footer at the
// bottom. The column is the designs' (mockups/home, mockups/app): 1152 px of content under the
// header's, 24 px at the sides (16 px on a phone), 28 px above and 40 px below (20 and 28 px on a
// phone). It is a flex column, so the chart can take the height the rest of the page leaves
// (CandleChart.tsx). At least as tall as the visible screen (dvh: on a phone without the address
// bar), 100vh where the browser has no dvh. `app` marks the signed-in app, where the system's
// reduced motion turns off every animation (index.css).
export function PageFrame({
  header,
  app = false,
  children,
}: {
  header: ReactNode;
  app?: boolean;
  children: ReactNode;
}) {
  return (
    <div data-app={app || undefined} className="flex min-h-screen flex-col supports-[height:100dvh]:min-h-dvh">
      {header}
      <main className="mx-auto flex w-full max-w-[75rem] flex-1 flex-col pt-7 pr-[max(24px,env(safe-area-inset-right,0px))] pb-10 pl-[max(24px,env(safe-area-inset-left,0px))] max-sm:pt-5 max-sm:pr-[max(16px,env(safe-area-inset-right,0px))] max-sm:pb-7 max-sm:pl-[max(16px,env(safe-area-inset-left,0px))]">
        {children}
      </main>
      <Footer />
    </div>
  );
}

// The public pages under the site's header: the route's page, or the one given (not found).
export function Layout({ children }: { children?: ReactNode }) {
  return <PageFrame header={<Header />}>{children ?? <Outlet />}</PageFrame>;
}

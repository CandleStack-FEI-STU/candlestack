import { Outlet } from '@tanstack/react-router';

import { Footer } from '@/components/Footer';
import { Header } from '@/components/Header';

// Every page: the header on top, the page itself in a centered column below, the footer at the
// bottom. The column is wide (1536 px) because the chart page needs the room on big screens. It
// is a flex column, so the chart can take the height the rest of the page leaves (CandleChart.tsx).
// At least as tall as the visible screen (dvh: on a phone without the address bar), 100vh where
// the browser has no dvh.
export function Layout() {
  return (
    <div className="flex min-h-screen flex-col supports-[height:100dvh]:min-h-dvh">
      <Header />
      <main className="mx-auto flex w-full max-w-[96rem] flex-1 flex-col px-4 py-8 lg:px-8">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}

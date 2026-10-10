import { Outlet } from '@tanstack/react-router';

import { Header } from '@/components/Header';

// Every page: the header on top, the page itself in a centered column below. The column is
// wide (1536 px) because the chart page needs the room on big screens.
export function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="mx-auto w-full max-w-[96rem] flex-1 px-4 py-8 lg:px-8">
        <Outlet />
      </main>
    </div>
  );
}

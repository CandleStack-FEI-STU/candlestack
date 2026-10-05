import { Outlet } from '@tanstack/react-router'

import { Header } from '@/components/Header'

// Every page: the header on top, the page itself in a centered column below.
export function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}

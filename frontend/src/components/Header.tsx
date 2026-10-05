import { Link } from '@tanstack/react-router'

import { Logo } from '@/brand/Logo'
import { ApiStatus } from '@/components/ApiStatus'
import { ThemeToggle } from '@/components/ThemeToggle'

export function Header() {
  return (
    <header className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <Link to="/" aria-label="CandleStack home" className="rounded-md">
          <Logo />
        </Link>
        <div className="flex items-center gap-3">
          <ApiStatus />
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}

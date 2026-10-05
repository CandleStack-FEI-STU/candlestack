import { useCallback, useSyncExternalStore } from 'react'

export type Theme = 'dark' | 'light'

// The same key is read by public/theme.js before the page paints.
const STORAGE_KEY = 'candlestack-theme'

function current(): Theme {
  return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark'
}

function apply(theme: Theme) {
  document.documentElement.dataset.theme = theme
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    // Storage can be blocked (private mode); the theme still applies for this page.
  }
  listeners.forEach((listener) => listener())
}

const listeners = new Set<() => void>()

function subscribe(listener: () => void) {
  listeners.add(listener)
  // Another tab changed the theme: follow it.
  const onStorage = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY) {
      document.documentElement.dataset.theme = event.newValue === 'light' ? 'light' : 'dark'
      listener()
    }
  }
  window.addEventListener('storage', onStorage)
  return () => {
    listeners.delete(listener)
    window.removeEventListener('storage', onStorage)
  }
}

export function useTheme() {
  const theme = useSyncExternalStore(subscribe, current)
  const toggle = useCallback(() => apply(current() === 'dark' ? 'light' : 'dark'), [])
  return { theme, toggle }
}

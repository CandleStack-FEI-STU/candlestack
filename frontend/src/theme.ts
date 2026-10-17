import { useSyncExternalStore } from 'react';

import type { Theme } from '@/api';

// The theme on the page: data-theme on <html>, kept in localStorage so the next visit starts with
// it. Signed in, the account's theme (Settings, Appearance) wins and this is its cache, so the
// page never flashes the other theme while the account's is on its way.

// The same key is read by public/theme.js before the page paints.
const STORAGE_KEY = 'candlestack-theme';

function current(): Theme {
  return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
}

const listeners = new Set<() => void>();

export function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Storage can be blocked (private mode); the theme still applies for this page.
  }
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  // Another tab changed the theme: follow it.
  const onStorage = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY) {
      document.documentElement.dataset.theme = event.newValue === 'light' ? 'light' : 'dark';
      listener();
    }
  };
  window.addEventListener('storage', onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener('storage', onStorage);
  };
}

export function useTheme(): Theme {
  return useSyncExternalStore(subscribe, current);
}

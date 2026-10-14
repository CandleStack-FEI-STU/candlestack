import { useCallback, useSyncExternalStore } from 'react';

// Whether a CSS media query matches now, updated when it changes; true where there is no window
// (server-side rendering in tests), the wide layout.
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const list = window.matchMedia(query);
      list.addEventListener('change', onChange);
      return () => list.removeEventListener('change', onChange);
    },
    [query],
  );
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    () => true,
  );
}

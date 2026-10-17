// Reduce motion (Settings, Appearance): data-motion="reduce" on <html>, which index.css reads
// like the system's prefers-reduced-motion. Kept in localStorage as the cache of the account's
// setting, so public/theme.js sets it before the page paints and no animation plays meanwhile.

// The same key is read by public/theme.js.
const STORAGE_KEY = 'candlestack-reduce-motion';

export function applyReduceMotion(reduce: boolean) {
  const root = document.documentElement;
  if (reduce) root.dataset.motion = 'reduce';
  else delete root.dataset.motion;
  try {
    if (reduce) localStorage.setItem(STORAGE_KEY, 'true');
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Storage can be blocked (private mode); the setting still applies for this page.
  }
}

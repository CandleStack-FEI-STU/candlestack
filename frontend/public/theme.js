// Applies the saved theme and Reduce motion before the page paints, so a light-theme user never
// sees a dark flash and no animation plays before the app knows the account's settings. Dark is
// the default (data-theme in index.html). A separate file, not inline in index.html, because the
// CSP allows only scripts from our own host.
// Keep the keys in sync with src/theme.ts and src/motion.ts.
try {
  if (localStorage.getItem('candlestack-theme') === 'light') {
    document.documentElement.dataset.theme = 'light';
  }
  if (localStorage.getItem('candlestack-reduce-motion') === 'true') {
    document.documentElement.dataset.motion = 'reduce';
  }
} catch {
  // Storage blocked (private mode): stay dark, with motion.
}

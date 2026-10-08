// Applies the saved theme before the page paints, so a light-theme user never sees a dark
// flash. Dark is the default (data-theme in index.html). A separate file, not inline in
// index.html, because the CSP allows only scripts from our own host.
// Keep the key in sync with src/theme.ts.
try {
  if (localStorage.getItem('candlestack-theme') === 'light') {
    document.documentElement.dataset.theme = 'light';
  }
} catch {
  // Storage blocked (private mode): stay dark.
}

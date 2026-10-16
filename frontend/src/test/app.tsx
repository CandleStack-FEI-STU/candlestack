import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider, createMemoryHistory } from '@tanstack/react-router';
import { render } from '@testing-library/react';

import { createAppRouter } from '@/router';

// Radix measures and captures the pointer, and the router restores the scroll position, through
// browser APIs jsdom lacks.
function polyfillDom() {
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  Object.assign(Element.prototype, {
    hasPointerCapture: () => false,
    releasePointerCapture: () => undefined,
    scrollIntoView: () => undefined,
  });
  window.scrollTo = () => undefined;
}

// The whole app on `url` in jsdom, with a fresh query client that never retries: the routes, their
// guards and loaders, then the page. Answers come from a stubbed fetch (src/test/api.ts).
export async function renderApp(url: string) {
  polyfillDom();
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createAppRouter({ queryClient }, createMemoryHistory({ initialEntries: [url] }));
  await router.load();
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { router, queryClient };
}

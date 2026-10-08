import type { QueryClient } from '@tanstack/react-query';
import { createRootRouteWithContext, createRoute, createRouter } from '@tanstack/react-router';

import { queryClient } from '@/api';
import { Layout } from '@/components/Layout';
import { InstrumentPage } from '@/pages/InstrumentPage';
import { InstrumentsPage } from '@/pages/InstrumentsPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { validateInstrumentSearch } from '@/routes/instrumentSearch';

// Every route gets the query client, so a route loader can fetch its data before it renders.
type RouterContext = { queryClient: QueryClient };

const rootRoute = createRootRouteWithContext<RouterContext>()({
  component: Layout,
  notFoundComponent: NotFoundPage,
});

const instrumentsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: InstrumentsPage,
});

// /instrument/crypto:BTCUSDT?tf=1h; the search params are checked once, in validateSearch.
const instrumentRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/instrument/$id',
  validateSearch: validateInstrumentSearch,
  component: InstrumentPage,
});

const routeTree = rootRoute.addChildren([instrumentsRoute, instrumentRoute]);

export const router = createRouter({
  routeTree,
  context: { queryClient },
  // Start loading a page when the user hovers or focuses its link.
  defaultPreload: 'intent',
  // TanStack Query decides when data is stale, not the router.
  defaultPreloadStaleTime: 0,
  // Instrument ids contain ':' (crypto:BTCUSDT); keep it readable instead of %3A.
  pathParamsAllowedCharacters: [':'],
});

// Makes routes, params and search params type-checked everywhere (Link, useParams, useSearch).
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}

import type { QueryClient } from '@tanstack/react-query'
import { createRootRouteWithContext, createRoute, createRouter } from '@tanstack/react-router'

import { parseTimeframe, queryClient, type Timeframe } from '@/api'
import { Layout } from '@/components/Layout'
import { InstrumentPage } from '@/pages/InstrumentPage'
import { InstrumentsPage } from '@/pages/InstrumentsPage'
import { NotFoundPage } from '@/pages/NotFoundPage'

// Every route gets the query client, so a route loader can fetch its data before it renders.
type RouterContext = { queryClient: QueryClient }

const rootRoute = createRootRouteWithContext<RouterContext>()({
  component: Layout,
  notFoundComponent: NotFoundPage,
})

const instrumentsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: InstrumentsPage,
})

// /instrument/crypto:BTCUSDT?tf=1h. The search params are checked here, once: a broken link
// like ?tf=banana opens the default timeframe instead of breaking the page.
export type InstrumentSearch = { tf: Timeframe }

const instrumentRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/instrument/$id',
  validateSearch: (search: Record<string, unknown>): InstrumentSearch => ({
    tf: parseTimeframe(search.tf),
  }),
  component: InstrumentPage,
})

const routeTree = rootRoute.addChildren([instrumentsRoute, instrumentRoute])

export const router = createRouter({
  routeTree,
  context: { queryClient },
  // Start loading a page when the user hovers or focuses its link.
  defaultPreload: 'intent',
  // TanStack Query decides when data is stale, not the router.
  defaultPreloadStaleTime: 0,
})

// Makes routes, params and search params type-checked everywhere (Link, useParams, useSearch).
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

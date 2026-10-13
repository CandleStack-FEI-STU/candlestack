# Frontend stack

Tools for the real frontend ([#110](https://github.com/CandleStack-FEI-STU/candlestack/issues/110)).
Limits that shaped the choice:

- prod serves the frontend as static files (Caddy), so the app must build to HTML, JS and CSS;
- the API has no CORS headers, and candle and instrument-detail requests are limited to 60 per
  minute (search is not);
- the chart shows crypto (24/7) and US stocks (no candles at night, on weekends and holidays).

| Area | Pick |
| --- | --- |
| Framework | React + TypeScript + Vite |
| Routing | TanStack Router |
| UI | shadcn/ui + Tailwind CSS |
| Chart | Lightweight Charts |
| API | TanStack Query, all calls in one module |

## Framework

| Option | Pro | Con |
| --- | --- | --- |
| React + Vite | static build, fits the current container; most libraries support React | routing is a separate library |
| Svelte | less code, small bundles | fewer libraries for UI and charts |
| Next.js | routing and layouts built in | made for a Node server; as static export most features are off |

**Pick: React + Vite.** The Dockerfile only gets a Node build step, Caddy stays.

## Routing

| Option | Pro | Con |
| --- | --- | --- |
| TanStack Router | typed routes and links; search params validated by a schema; route loaders work with TanStack Query | newer, smaller community |
| React Router | most used, simple | search params are plain strings, every page parses and checks them itself |
| Wouter | tiny | no search param handling, no loaders |

**Pick: TanStack Router.** Later pages keep a whole experiment in the URL (model, threshold,
stop loss, fill, period), so a link can be shared. Each route declares its search params with
a schema: a broken or outdated link falls back to defaults or shows an error instead of
crashing the page. A route can preload its data through TanStack Query before it renders.

## UI and styling

| Option | Pro | Con |
| --- | --- | --- |
| shadcn/ui + Tailwind | components live in our repo; accessible (Radix); theme is CSS variables | long class lists |
| Mantine | full component set, fast start | own look, hard to get the Vercel / Linear style |
| CSS Modules | no dependencies | every dropdown and dialog written by hand |

**Pick: shadcn/ui + Tailwind.** Colors, font and theme sit in one CSS file, one set for dark
and one for light, which is what #111 needs. Teal `#0f766e` / `#3cc7a6` and Geist stay.

## Chart

| Option | Pro | Con |
| --- | --- | --- |
| Lightweight Charts | candles + volume; stock sessions join without gaps; easy "scroll left, load more"; small | only price charts; time is UTC |
| ECharts | any chart type | large; nights and weekends show as empty gaps |
| Recharts | simple React API | no candlesticks; slow with thousands of points |

**Pick: Lightweight Charts.** It covers #113 as is. Stock times need a formatter to show New
York time, and candle colors must differ from the teal accent.

## API

| Option | Pro | Con |
| --- | --- | --- |
| TanStack Query | cache, merges duplicate requests, loading and error states, infinite loading | one more library to learn |
| SWR | smaller, same idea | weaker infinite loading |
| `fetch` in `useEffect` | no dependency | no cache; easy to hit the rate limit |

**Pick: TanStack Query.** The cache keeps candle and instrument-detail requests under 60 per
minute.

- All API calls live in `src/api/`, so the API changes (#104–#109) are fixed in one place.
- In dev, the Vite proxy sends `/api` to `https://app.candlestack.tech` (no CORS problem).
  In prod the API is on the same host.

## Rules

- **Same origin only.** The CSP (`infra/edge/caddy/Caddyfile`, report-only for now) allows
  scripts and fonts from our own host. No CDN: Geist comes from npm
  (`@fontsource-variable/geist`), and the theme script is its own file, not inline in
  `index.html`.
- **Typed API.** Response types are generated from `docs/openapi.json` with
  `openapi-typescript`, so the API changes (#104–#109) show up as type errors.
- **Caching.** Older candle pages never change and are cached for long. The latest page
  refreshes at most once a minute. No automatic retry on 429: the page shows "try again in N s"
  counting down from `Retry-After`.
- **Gaps.** When `meta.gaps_total > 0`, the chart shows a small note: it joins sessions, so
  real gaps in the data would be hidden otherwise.

## Instrument icons

`src/components/InstrumentIcon.tsx` shows the icon of `GET /api/v1/data/instruments/{id}/icon`
(the logo from logo.dev or the backend's fallback, `docs/data.md`) in three places:

| Place | Size | Corner radius | Row |
| --- | --- | --- | --- |
| Instrument list, before the symbol | 32 px | 3.2 px | 41 px (4 px padding), as high as without it |
| Header quick search, before the symbol | 32 px | 3.2 px | 44 px |
| Instrument page header, next to the name | 64 px | 6.4 px | - |

- The radius is 10 % of the size. The fallback SVG is square, so the frontend rounds it like a
  logo; a rounding of its own would show the white tile in its corners.
- Every icon sits on a white tile in both themes: many logos have a transparent background, and
  black ones such as Apple's would disappear on the dark background. The image fills the tile
  1 px inside its edge, clipped to its corners, under a 1 px hairline (a solid grey in dark
  mode: a translucent white would leave a light rim), so no logo runs over the edge.
- The image is same-origin (allowed by the CSP), `loading="lazy"`, with a fixed width and height
  so rows do not jump while it loads, and an empty `alt`: the symbol is always next to it.
- In the list, the icon is not a link of its own: the symbol's link still covers the whole row.
- On phones (< 640 px) the quick-search list hangs from the header with a 16 px gutter on both
  sides; from `sm` up it is right-aligned under the search box.

## Licenses

| Library | License |
| --- | --- |
| React, Vite, Tailwind, shadcn/ui, TanStack Query, TanStack Router, openapi-typescript | MIT |
| TypeScript, Lightweight Charts | Apache 2.0 |
| Geist font | SIL Open Font License 1.1 |

Lightweight Charts asks for a TradingView attribution, and logo.dev's free plan for a link to
Logo.dev (the instrument icons, `docs/data.md`). Both are a line in the footer of every page
(`src/components/Footer.tsx`); the chart is created with `attributionLogo: false`, so it shows no
logo of its own.

## Prototype

A small prototype (not in this PR) shows 500 BTCUSDT candles with volume from the prod API
using this stack. The build is about 130 kB gzipped.

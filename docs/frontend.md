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

## Licenses

| Library | License |
| --- | --- |
| React, Vite, Tailwind, shadcn/ui, TanStack Query, TanStack Router, openapi-typescript | MIT |
| TypeScript, Lightweight Charts | Apache 2.0 |
| Geist font | SIL Open Font License 1.1 |

Lightweight Charts asks for a TradingView attribution; its default logo on the chart covers it.

## Prototype

A small prototype (not in this PR) shows 500 BTCUSDT candles with volume from the prod API
using this stack. The build is about 130 kB gzipped.

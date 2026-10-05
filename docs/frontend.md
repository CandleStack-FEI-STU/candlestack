# Frontend stack

Tools for the real frontend ([#110](https://github.com/CandleStack-FEI-STU/candlestack/issues/110)).
Limits that shaped the choice:

- prod serves the frontend as static files (Caddy), so the app must build to HTML, JS and CSS;
- the API has no CORS headers and allows 60 requests per minute;
- the chart shows crypto (24/7) and US stocks (no candles at night, on weekends and holidays).

| Area | Pick |
| --- | --- |
| Framework | React + TypeScript + Vite, React Router |
| UI | shadcn/ui + Tailwind CSS |
| Chart | Lightweight Charts |
| API | TanStack Query, all calls in one module |

## Framework

| Option | Pro | Con |
| --- | --- | --- |
| React + Vite | static build, fits the current container; most libraries support React | routing is a separate library |
| Svelte | less code, small bundles | fewer libraries for UI and charts |
| Next.js | routing and layouts built in | made for a Node server; as static export most features are off |

**Pick: React + Vite.** The Dockerfile only gets a Node build step, Caddy stays. React Router
keeps the page and timeframe in the URL (`/instrument/crypto:BTCUSDT?tf=1h`, #113).

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

**Pick: TanStack Query.** The cache keeps us under 60 requests per minute.

- All API calls live in `src/api/`, so the API changes (#104–#109) are fixed in one place.
- A 429 shows "try again in N s" from `Retry-After`.
- In dev, the Vite proxy sends `/api` to `https://app.candlestack.tech` (no CORS problem).
  In prod the API is on the same host.

## Licenses

| Library | License |
| --- | --- |
| React, React Router, Vite, Tailwind, shadcn/ui, TanStack Query | MIT |
| TypeScript, Lightweight Charts | Apache 2.0 |

Lightweight Charts asks for a TradingView attribution; its default logo on the chart covers it.

## Prototype

A small prototype (not in this PR) shows 500 BTCUSDT candles with volume from the prod API
using this stack. The build is about 130 kB gzipped.

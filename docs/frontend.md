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
- **Pages by count.** The chart asks for candles by number, not by time, and the API counts
  them by the market schedule (stocks: sessions only). A page is `limit=min(500, max_candles)`
  candles. The latest page is always the last of them (`?limit=…`); the older pages hang below
  its start at the first scroll to the left (the anchor), each ending where the one above it
  begins (`?end=<meta.start>&limit=…`). Older pages never change and stay cached. When the
  refreshed latest page has moved on above the anchor, a bridge asks for the
  `min(1000, max_candles)` candles before its start (`?end=<its start>&limit=…`); the candles
  from the anchor on fill the gap, so none go missing after an idle tab. Until the bridge
  arrives, or while it fails (to be retried), the chart keeps showing the latest page and the
  bridge as they were, and the new candles wait. History starts over below the latest page when
  the bridge begins above the anchor (more than 1000 candles went by) or the API cannot give it
  (`too-many-candles`, `period-out-of-range`). History ends at the first candle
  (`available_from`), at a page that starts at its end, or after three older pages in a row
  without candles (one or two are an outage).
- **Gaps.** When `meta.gaps_total > 0`, the chart shows a small note: it joins sessions, so
  real gaps in the data would be hidden otherwise.
- **Phones.** Every page fits a 360 px screen without sideways scrolling, in both themes. Long
  text gives way instead of the layout: the instrument list has fixed column widths (see
  [Instrument list](#instrument-list); the name takes the rest), so names, symbols and exchanges
  truncate (their title shows them in full); an instrument's id and name wrap, and error messages
  break their long paths (`break-words`). Below `sm` the instrument page shows the symbol fact only to
  screen readers (it ends the id above the name) and narrows the gaps of the facts and the
  timeframe switch, so each fits one line.
- **Chart height.** The layout is at least as tall as the visible screen (`100dvh`, `100vh`
  without dvh) and the page is a flex column (`Layout.tsx`). The candles section, also while it
  loads or fails, and the chart in it are the part that grows: the chart takes the height the
  header, the instrument info, the switch, the status line and the footer leave, however many
  lines they take. At least 16rem on a phone and 20rem from `sm` up, below that the page
  scrolls; the section stops at 64rem (the chart at about 60rem), and on a taller screen the
  space left stays below it. `chartHeight.test.tsx` checks every link of that chain.

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
- When the image does not load at all (e.g. a 502 during a deploy), the tile draws the backend's
  fallback itself (Lucide's `chart-candlestick` in white on dark grey), never a broken image.
- In the list, the icon is not a link of its own: the symbol's link still covers the whole row.
- On phones (< 640 px) the quick-search list hangs from the header's bar (`Header.tsx`, its
  positioning parent) with a 16 px gutter on both sides; from `sm` up it is right-aligned under
  the search box and never wider than the screen.

## Instrument list

The list (`src/features/instruments/InstrumentTable.tsx`, #184) opens with the most traded
instruments first and shows each one's 24 h stats from the API (`price`, `change_24h`,
`volume_24h`, see [data.md](data.md#stats)):

| Column | Width | Content |
| --- | --- | --- |
| Symbol | 168 px | 32 px icon, 10 px gap, the symbol (the row's link) |
| Price | 128 px, right | 2 decimals from 10 (83,249.35), 4 between 1 and 10 (1.3662), up to 4 significant digits below 1 (0.08438, 0.0000042) |
| 24h | 104 px, right | an 8 px triangle and the change without a sign, 2 decimals (1.51%); up `--up` (#1a7f37, dark #43b049), down `--down`, 0.00% muted without a triangle |
| Volume 24h | 112 px, right | USD with 3 significant digits ($1.26B, $685M, $62K) |
| Name | the rest | muted, one line with an ellipsis |
| Type | 88 px | Stock or Crypto, muted; from `lg` (1024 px) |
| Exchange | 104 px | muted |

- Numbers are in Geist Mono, rows 41 px (cell padding 4 12). Without stats the price, change and
  volume are "—". No market open or closed hint: a stock shows its last price.
- The header is 12/16 medium and muted; the sorted column's header is ink with a 12 px arrow:
  Volume 24h ↓ (default), 24h ↓ (Top gainers) or ↑ (Top losers), Symbol ↑.
- Phones (below `md`, 768 px): two columns. The symbol over "exchange · volume" (12/14; "NYSE ·
  no stats yet"), and in 100 px the price over the change with its sign (+1.51%, −0.71%; "No
  stats yet"). The header says "Symbol · by volume ↓", "Symbol ↑", "Price", or "Price · 24h ↓/↑"
  when sorted by change. Cells have 8 px between the columns and 12 px at the sides.
- From `md` to `lg` the Type column is left out, so the name keeps about 100 px at 768 px; from
  `lg` every column shows. Nothing scrolls sideways at any width.
- The formats are pure functions with unit tests (`numbers.ts`).
- The 10-day mini chart of the approved design comes with #189.

## Instrument filters

The list filters by type (the market) and exchange and sorts by 24 h volume, change or symbol,
all in the URL (`/?market=stock&exchange=NYSE`, `/?exchange=BINANCE`, `/?sort=gainers`), behind one
**Filters** button (`src/features/instruments/Filters.tsx`, rules in `filterRules.ts` and
`sorting.ts`, #182, #184):

- The button is 34 × 200 px whatever it says ("All instruments", "Stocks · NYSE", "Crypto ·
  Binance", "Top gainers", "Stocks · Top losers"), so nothing in the row moves when the filters
  change. Its panel is 412 px wide (Type over Sort by in the 128 px left column, Exchange on the
  right, 12 px padding, at most 480 px high), right-aligned under it. On phones Type and Sort by
  sit side by side with Exchange below, the panel is the screen width minus 32 px and tightened
  (8 px padding and gaps, headings 4 px above their list, group labels 24 px, 2 px around the
  separators) to 476 px, so every entry shows without scrolling.
- Sort by: Volume (the default, left out of the URL), Top gainers (`?sort=gainers`), Top losers
  (`?sort=losers`) and Symbol (`?sort=symbol`); the API gets `sort=change`, `-change` or `symbol`.
  The summary adds any order but Volume. With a query the search ranking stays first and the
  order only breaks its ties.
- Exchange: All exchanges, then the stock exchanges (NASDAQ, NYSE, ARCA, AMEX, BATS), then the
  crypto exchanges (Binance). Under Stocks, Binance is disabled and marked "Crypto only"; under
  Crypto, the stock exchanges are disabled and marked "Stocks only": shown, not hidden, so the
  list keeps its shape and says why. Under All every exchange can be picked, and Type stays All.
- Changing the type keeps an exchange it has and drops one it does not; picking an exchange
  never changes the type, and an order changes neither. Every pick starts at page 1 and adds a history entry, so Back undoes
  it; the panel stays open for the second pick.
- A link the panel cannot make (`/?market=crypto&exchange=NYSE`) shows an empty list that says
  why ("No crypto pairs on NYSE", "NYSE lists stocks only.") with a "Show all exchanges" link,
  and the panel shows NYSE chosen but disabled.
- Keyboard: Enter, Space or ArrowDown on the button opens the panel on the chosen type. The
  arrows, Home and End move through the sections (Type, Sort by, Exchange) and skip disabled
  entries, ArrowLeft and ArrowRight go to the previous or next section, a letter jumps to the next entry starting with it, and
  Enter or Space picks. Escape closes the panel and the focus returns to the button; Tab and
  Shift+Tab close it and move on to the element after or before the button, like leaving any
  other control; a click outside closes it too. Each section is an ARIA listbox; the focus
  itself moves between its options.
- The panel is a shadcn/ui Popover (`src/components/ui/popover.tsx`, `@radix-ui/react-popover`):
  it places the panel, keeps it on the screen and closes it on Escape or a click outside.

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

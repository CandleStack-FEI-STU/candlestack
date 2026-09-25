# Market data contract

The `data` module serves instruments and candles for two markets: crypto from Binance and US
stocks from Alpaca. Nothing is stored: data is fetched from the source on request, validated,
cached in Redis and returned. This document is the contract for the `/api/v1/data` endpoints
and for the code behind them. Architecture and configuration: [architecture.md](architecture.md).

## Sources

| Market | Source | Feed | Instruments | Candles | Auth |
| --- | --- | --- | --- | --- | --- |
| `crypto` | Binance spot | `spot` | `GET /api/v3/exchangeInfo`: every symbol with `status` `TRADING` | kline archives on `data.binance.vision`, newest days from `GET /api/v3/klines` | none |
| `stock` | Alpaca, paper account | `iex` | `GET /v2/assets?status=active&asset_class=us_equity`: `tradable` true, `exchange` not `OTC` (US equities and ETFs) | `GET /v2/stocks/bars` with `feed=iex` and `adjustment=all`; trading days from `GET /v2/calendar` | `APCA-API-KEY-ID`, `APCA-API-SECRET-KEY` headers |

- One source per market; sources are never mixed within one series.
- History: Binance from each pair's listing, Alpaca from 2016.
- Binance: spot only (no futures, no margin). Volume is in the base asset (BTC for BTCUSDT).
- Alpaca IEX is the free feed: prices are IEX trades and volume is IEX volume only, a small
  share of the consolidated volume. `feed=iex` is always sent explicitly.
- `adjustment=all` applies splits and dividends to the whole history, so past stock candles
  change after a corporate action (see [Fingerprint](#fingerprint)).

## Instruments

Instrument id: `<market>:<symbol>`, for example `crypto:BTCUSDT`, `stock:AAPL`, `stock:BRK.B`.
Parsing trims whitespace, lower-cases the market and upper-cases the symbol
(`crypto:btcusdt` is `crypto:BTCUSDT`). Symbols are spelled as the source spells them: letters
and digits of any script (Binance lists pairs such as `币安人生USDT`) and dots, at most 32
characters.

| Field | Crypto | Stock |
| --- | --- | --- |
| `id` | `crypto:BTCUSDT` | `stock:AAPL` |
| `market` | `crypto` | `stock` |
| `symbol` | `BTCUSDT` | `AAPL` |
| `name` | `BTC/USDT` (base/quote) | Alpaca asset name |
| `source` | `binance` | `alpaca` |
| `feed` | `spot` | `iex` |
| `exchange` | `null` | Alpaca exchange (`NASDAQ`, `NYSE`, `ARCA`, ...) |
| `base`, `quote` | `BTC`, `USDT` | `null` |

`GET /api/v1/data/instruments?q=&market=&limit=` searches the cached catalogs of both markets
(no source call per item) and returns `{"items": [<instrument>, ...]}`.

| Parameter | Rule |
| --- | --- |
| `q` | required; an empty query returns no items. Case-insensitive; separators are ignored in symbols: `btc/usdt`, `btc-usdt` and `BTC USDT` all match `BTCUSDT`, `brkb` matches `BRK.B` |
| `market` | optional, `crypto` or `stock` |
| `limit` | default 20, max 100 |

Ranking: exact symbol, symbol prefix, prefix of a word in the name, substring of the symbol,
substring of the name. Ties: shorter symbol first, then alphabetical.

`GET /api/v1/data/instruments/{id}` returns the instrument plus what a client needs to build a
valid `/candles` request (404 `instrument-not-found` if the id is not in the catalog):

```json
{
  "id": "stock:AAPL",
  "market": "stock",
  "symbol": "AAPL",
  "name": "Apple Inc. Common Stock",
  "source": "alpaca",
  "feed": "iex",
  "exchange": "NASDAQ",
  "base": null,
  "quote": null,
  "timeframes": ["1m", "5m", "15m", "1h", "4h", "1d"],
  "available_from": 1451917800,
  "max_candles": 50000
}
```

`available_from` is the open time of the instrument's first candle; `max_candles` is
`CANDLES_MAX`. Values in the examples of this document are illustrative.

## Timeframes

Both markets have the same list.

| Timeframe | Seconds | Crypto | Stock |
| --- | --- | --- | --- |
| `1m` | 60 | Binance `1m` | Alpaca `1Min`, regular session only |
| `5m` | 300 | Binance `5m` | built from 1m |
| `15m` | 900 | Binance `15m` | built from 1m |
| `1h` | 3600 | Binance `1h` | built from 1m, aligned to the session open |
| `4h` | 14400 | Binance `4h` | built from 1m, two candles per session |
| `1d` | 86400 | Binance `1d` | see [4h and 1d](#4h-and-1d) |

## Time

- All times in requests and responses are UTC epoch seconds (integers).
- A candle is labelled by its open time `t`.
- A request covers `[start, end)`: a candle is returned when `start <= t < end`. `start` and
  `end` do not have to be aligned to the timeframe.
- Only closed candles are returned: the candle's end (`t` + duration, for stocks at most the
  session close) must be at or before the request time. The candle still in progress never
  appears and is not a gap.
- Crypto bins are aligned to UTC epoch multiples of the timeframe (1d starts at 00:00 UTC,
  4h at 00:00, 04:00, ..., 20:00 UTC).

## Stock sessions and calendar

- Regular session only: 09:30-16:00 America/New_York. Early-close days end at 13:00 (for
  example 2024-11-29 and 2024-12-24). Holidays have no session. Pre-market and after-hours
  bars are dropped.
- Trading days, opens and closes come from Alpaca `GET /v2/calendar` (`date`, `open`, `close`
  in New York time), cached 7 days, converted to UTC with `zoneinfo`, so DST is handled: the
  open is 14:30 UTC in winter and 13:30 UTC in summer.
- Bins are aligned to the session open. The last bin of a session ends at the close and can be
  shorter than the timeframe.

| Timeframe | Normal day (09:30-16:00), bin opens in New York time | Candles | Early close (09:30-13:00) | Candles |
| --- | --- | --- | --- | --- |
| `1m` | 09:30, 09:31, ..., 15:59 | 390 | 09:30, ..., 12:59 | 210 |
| `5m` | 09:30, 09:35, ..., 15:55 | 78 | 09:30, ..., 12:55 | 42 |
| `15m` | 09:30, 09:45, ..., 15:45 | 26 | 09:30, ..., 12:45 | 14 |
| `1h` | 09:30, 10:30, ..., 14:30, 15:30 (30 min) | 7 | 09:30, 10:30, 11:30, 12:30 (30 min) | 4 |
| `4h` | 09:30-13:30, 13:30-16:00 | 2 | 09:30-13:00 | 1 |
| `1d` | 09:30-16:00 | 1 | 09:30-13:00 | 1 |

## 4h and 1d

| | Crypto | Stock |
| --- | --- | --- |
| `4h` | native Binance 4h, six UTC bins per day | 09:30-13:30 and 13:30-close; one candle on early-close days |
| `1d` | native Binance 1d, 00:00-24:00 UTC | one candle per session, labelled with the session open in UTC |

Stock `1d` source: Alpaca `1Day` bars if they reflect the regular session only, otherwise
built from regular-session 1m bars. The source spike decides this (see
[Facts](#facts-verified-against-the-sources)).

## What is fetched

Candles are fetched and cached per calendar month (UTC) of one instrument and timeframe.

**Crypto** (`BINANCE_DATA_URL`, `BINANCE_API_URL`)

| Part of the period | Where from |
| --- | --- |
| closed month with a published monthly archive | `data/spot/monthly/klines/<SYMBOL>/<tf>/<SYMBOL>-<tf>-<YYYY-MM>.zip` |
| days of the current month, and of a closed month whose monthly archive is not published yet | `data/spot/daily/klines/<SYMBOL>/<tf>/<SYMBOL>-<tf>-<YYYY-MM-DD>.zip` |
| newest days without a daily archive | `GET /api/v3/klines?symbol=&interval=&startTime=&endTime=&limit=1000` |

- Every archive is verified against its `<file>.CHECKSUM` (SHA-256) before it is read.
- Archive CSV columns used: open time, open, high, low, close, volume (the first six).
- Archive timestamps are microseconds in files from 2025-01-01 on and milliseconds before;
  both are converted to seconds.

**Stocks** (`ALPACA_DATA_URL`, `ALPACA_API_URL`)

- `GET /v2/stocks/bars` with `feed=iex`, `adjustment=all`, `timeframe=1Min` (plus `1Day` if
  the 1d rule says so), following `next_page_token` until the month is complete.
- Bars outside the sessions of the calendar are dropped before anything is built.
- `available_from`: the first `1Day` bar from 2016-01-01.

## Gaps

- A gap is an expected candle that the source did not deliver. Expected candles: crypto,
  every aligned bin of the period; stocks, every session bin of the period.
- Gaps are never filled, interpolated or forward-filled. They are reported in `meta.gaps`:
  `missing` is the total number of missing candles, `ranges` lists merged `[start, end)`
  ranges, earliest first, at most 100. Consecutive missing candles form one range, for stocks
  also across a night or weekend; a range ends where its last missing candle ends (at most the
  session close).
- Typical causes: exchange maintenance and trading halts; minutes without any IEX trade
  (common for illiquid stocks at 1m, rare at 1h and above).
- Candles with zero volume are kept as delivered.

## Validation

Requests are checked in this order; the first failure is the answer.

| Check | Error |
| --- | --- |
| client rate limit | 429 `rate-limited` |
| parameters present and well-formed: instrument id, timeframe from the list, integer `start < end` | 422 `validation` |
| instrument in the catalog | 404 `instrument-not-found` |
| `start >= available_from` and `end <=` request time | 422 `period-out-of-range` |
| expected candle count `<= CANDLES_MAX` | 422 `too-many-candles` |

Source data is checked before it is cached:

- sorted by time; rows with the same timestamp collapse to one (the last wins)
- open, high, low and close are positive
- `low <= min(open, close)` and `high >= max(open, close)`
- volume is not negative
- timestamps strictly increase
- Binance archives match their checksum

Data that fails is not cached, the failure is logged, and the request gets 502
`source-data-invalid`.

## Fingerprint

A fingerprint is a short code computed from a candle set: the same candles for the same request
always give the same code, and changing any single number gives a different one. It does not
depend on the cache, row order or JSON formatting.

Later, an experiment stores the fingerprint of the data it ran on. When the same request later
returns a different fingerprint, the source changed its data (for example Alpaca re-adjusted
the history after a split, or Binance corrected a candle) and the old result is no longer
reproducible on current data.

- Format: `sha256:<64 hex digits>`.
- Input: source, feed, instrument id, timeframe, `start`, `end`, then `t`, open, high, low,
  close and volume of every candle in time order. The exact byte layout is documented on
  `fingerprint()` in `backend/src/candlestack/data/candles.py`.

## Limits

**Candles per response.** At most `CANDLES_MAX` (default 50000). The count is the number of
expected candles in `[start, end)` (session bins for stocks), computed before any source call.
The error suggests the smallest timeframe that fits, or the latest `end` that fits with the
requested timeframe.

**Rate limits.** Fixed one-minute windows (UTC minute) counted in Redis.

| Limit | Counted per | Default | When spent |
| --- | --- | --- | --- |
| Clients: `CLIENT_RATE_LIMIT` | client IP (`CF-Connecting-IP`, else the peer address); every `/candles` request, cached or not | 60 per minute, `0` disables | 429 `rate-limited` with `Retry-After` |
| Alpaca: `ALPACA_RATE_LIMIT` | environment; each Alpaca request | prod 150, stage 60, `pr-*` 30 | 503 `source-unavailable` with `Retry-After` |
| Binance REST: `BINANCE_WEIGHT_LIMIT` | environment; request weight of each REST call | 1000 | 503 `source-unavailable` with `Retry-After` |
| `data.binance.vision` | not limited | | |

- Alpaca allows 200 requests per minute per key. Prod has its own key; stage and previews
  share one, so stage plus four previews stay within it.
- Binance limits request weight per IP, and all environments on the VM share one IP.
- A 429 from a source is retried with backoff that honours `Retry-After`; when retries run
  out the request gets 503 `source-unavailable`.

## Cache

Redis, per environment, no persistence, `allkeys-lru`: anything can disappear and is fetched
again. Keys:

| Key | Value | Lifetime |
| --- | --- | --- |
| `data:v1:catalog:<market>` | instrument list of the market with its fetch time | refreshed when older than 24 h; the old list is served while one background task refreshes it |
| `data:v1:calendar` | NYSE sessions from 2016 on | 7 days |
| `data:v1:candles:<instrument>:<timeframe>:<YYYY-MM>` | one month of validated candles, Arrow IPC + zstd | closed month 30 days, current month 60 s |
| `data:v1:first:<instrument>` | `available_from` | 7 days |
| `data:v1:health:<source>` | reachability of the source | 60 s |
| `data:lock:<key>` | single-flight lock for a key being fetched | 30 s |
| `data:rl:client:<ip>:<minute>`, `data:rl:alpaca:<minute>`, `data:rl:binance:<minute>` | fixed-window counters | 60 s |

- Single-flight: the first request for a missing key takes the lock (`SET NX`), fetches and
  stores the value; concurrent requests for the same key wait for the value instead of calling
  the source again.
- `v1` changes when a value format changes, because Redis keeps its contents across deploys.
- `GET /api/health/sources` reports `ok` or `error` per source (Binance `GET /api/v3/ping`,
  Alpaca `GET /v2/clock`) from the 60 s health keys.

## Candles endpoint

`GET /api/v1/data/candles?instrument=<id>&timeframe=<tf>&start=<epoch s>&end=<epoch s>`

Processing: rate limit, validation, catalog lookup, period and count checks, then each month
of the period from the cache or the source (single-flight), concatenated, sliced to
`[start, end)`, closed candles only, gaps found, fingerprint computed.

Response (columnar arrays; index `i` of every array is one candle):

```json
{
  "meta": {
    "instrument": "crypto:BTCUSDT",
    "timeframe": "1h",
    "start": 1717200000,
    "end": 1717214400,
    "source": "binance",
    "feed": "spot",
    "fingerprint": "sha256:3b1f0c9e...",
    "count": 3,
    "gaps": {"missing": 1, "ranges": [[1717207200, 1717210800]]}
  },
  "t": [1717200000, 1717203600, 1717210800],
  "o": [67491.0, 67612.5, 67580.1],
  "h": [67700.0, 67650.0, 67640.0],
  "l": [67420.2, 67510.0, 67488.8],
  "c": [67612.4, 67540.3, 67601.9],
  "v": [512.31, 398.07, 421.55]
}
```

| Field | Meaning |
| --- | --- |
| `meta.instrument`, `meta.timeframe`, `meta.start`, `meta.end` | the request, normalised |
| `meta.source`, `meta.feed` | `binance`/`spot` or `alpaca`/`iex` |
| `meta.fingerprint` | see [Fingerprint](#fingerprint) |
| `meta.count` | number of candles returned |
| `meta.gaps` | `missing` candles in total and up to 100 `[start, end)` ranges |
| `t` | open times, epoch seconds, strictly increasing |
| `o`, `h`, `l`, `c`, `v` | open, high, low, close, volume as numbers |

## Errors

RFC 9457 `application/problem+json`, `type` `https://candlestack.tech/problems/<slug>`. The
`detail` says which limit fired and what to change.

| Status | Slug | When | Extensions |
| --- | --- | --- | --- |
| 404 | `instrument-not-found` | the id is not in the catalog | `instrument` |
| 422 | `validation` | missing or malformed parameters | `errors` (FastAPI validation details) |
| 422 | `period-out-of-range` | `start` before `available_from`, or `end` in the future | `instrument`, `timeframe`, `available_from`, `available_to` |
| 422 | `too-many-candles` | more than `CANDLES_MAX` expected candles | `requested`, `maximum` |
| 429 | `rate-limited` | client over `CLIENT_RATE_LIMIT` | `limit`; header `Retry-After` |
| 502 | `source-data-invalid` | source data failed validation | `source` |
| 503 | `source-unavailable` | source down or timing out, or our budget for it is spent | `source`; header `Retry-After` when the budget is spent |

`start` before the first candle (`available_to` is the request time):

```json
{
  "type": "https://candlestack.tech/problems/period-out-of-range",
  "title": "Period out of range",
  "status": 422,
  "detail": "crypto:BTCUSDT has 1h candles from 2017-08-17T04:00:00Z (1502942400). Set start to 1502942400 or later.",
  "instrument": "crypto:BTCUSDT",
  "timeframe": "1h",
  "available_from": 1502942400,
  "available_to": 1790424000
}
```

Too many candles (1m for 2024-01-01 to 2024-04-01):

```json
{
  "type": "https://candlestack.tech/problems/too-many-candles",
  "title": "Too many candles",
  "status": 422,
  "detail": "Requested 131040 candles, the maximum is 50000. Use 5m or a larger timeframe, or end the period at 2024-02-04T17:20:00Z (1707067200) or earlier.",
  "requested": 131040,
  "maximum": 50000
}
```

Client rate limit:

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/problem+json
Retry-After: 17

{
  "type": "https://candlestack.tech/problems/rate-limited",
  "title": "Too many requests",
  "status": 429,
  "detail": "More than 60 candle requests in one minute from this address. Retry in 17 seconds.",
  "limit": 60
}
```

Source unavailable:

```json
{
  "type": "https://candlestack.tech/problems/source-unavailable",
  "title": "Data source unavailable",
  "status": 503,
  "detail": "Alpaca did not answer in time. Try again in a minute.",
  "source": "alpaca"
}
```

## Facts verified against the sources

> **TODO (source spike):** replace this line with the facts measured against Binance and
> Alpaca (catalog sizes, archive format and timestamp units, daily archive lag, weights and
> rate-limit headers, Alpaca session and 1Day behaviour, earliest data, split adjustment) and
> the resulting decisions, including the stock 1d rule.

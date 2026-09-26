# Market data contract

The `data` module serves instruments and candles for two markets: crypto from Binance and US
stocks from Alpaca. Nothing is stored: data is fetched from the source on request, validated,
cached in Redis and returned. This document is the contract for the `/api/v1/data` endpoints
and for the code behind them. Architecture and configuration: [architecture.md](architecture.md).

## Sources

| Market | Source | Feed | Instruments | Candles | Auth |
| --- | --- | --- | --- | --- | --- |
| `crypto` | Binance spot | `spot` | `GET /api/v3/exchangeInfo?symbolStatus=TRADING&showPermissionSets=false`: every symbol with `status` `TRADING` | kline archives on `data.binance.vision`, newest days from `GET /api/v3/klines` | none |
| `stock` | Alpaca, paper account | `iex` | `GET /v2/assets?status=active&asset_class=us_equity`: `tradable` true, `exchange` not `OTC` (US equities and ETFs) | `GET /v2/stocks/bars` with `feed=iex` and `adjustment=all`; trading days from `GET /v2/calendar` | `APCA-API-KEY-ID`, `APCA-API-SECRET-KEY` headers |

- One source per market; sources are never mixed within one series.
- History: Binance from each pair's listing; Alpaca IEX from 2020-07-27, when the IEX feed
  starts (per instrument: its first `1Day` bar). Paper accounts are entitled to IEX data only,
  so the SIP feed, which starts in 2016, is not used.
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
(no source call per item) and returns
`{"items": [<instrument>, ...], "count": <n>, "unavailable": []}`.

| Parameter | Rule |
| --- | --- |
| `q` | required, 1-50 characters; a query without letters or digits finds nothing. Case-insensitive; separators are ignored in symbols: `btc/usdt`, `btc-usdt` and `BTC USDT` all match `BTCUSDT`, `brkb` matches `BRK.B` |
| `market` | optional, `crypto` or `stock` |
| `limit` | default 20, max 100 |

Ranking: the top pair of a crypto base asset equal to the query, the one whose quote asset has
the most pairs in the catalog (USDT, so `btc` finds `crypto:BTCUSDT` first, before the stock
`BTC`); exact symbol; the other pairs of that base asset, most common quote asset first; symbol
prefix; prefix of a word in the name; substring of the symbol; substring of the name. Other
ties: shorter symbol first, then alphabetical.

Once the catalog of one market is loaded, a search over both markets does not wait for the
other: it is loaded in the background (retried at most every 30 s while its source is down and
Redis does not have it), and until then the search answers from the loaded market and names
the missing one in `unavailable` (`["stock"]`). A search that can reach no requested market is
503 `source-unavailable`.

`GET /api/v1/data/instruments/{id}` returns the instrument plus what a client needs to build a
valid `/candles` request (404 `instrument-not-found` if the id is not in the catalog). It counts
against the client rate limit like `/candles`, because its first-candle lookup can call the
source:

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
  "available_from": 1595856600,
  "available_to": 1790380620,
  "max_candles": 50000
}
```

- `available_from`: open time of the instrument's first candle: the first 1m kline of a
  crypto pair, the session open of the first `1Day` bar of a stock; `null` when the source has
  no candle yet or cannot be asked. For a longer timeframe the first candle opens at the start
  of the bin that holds this moment (BTCUSDT: 1m from 2017-08-17T04:00Z, 1d from 00:00Z).
- `available_to`: open time of the newest closed 1m bin when the answer was made; for stocks
  the last minute of the latest session that has begun (15:59 New York after the close).
- `max_candles`: `CANDLES_MAX`.

Values in the examples of this document are illustrative.

## Timeframes

Both markets have the same list.

| Timeframe | Seconds | Crypto | Stock |
| --- | --- | --- | --- |
| `1m` | 60 | Binance `1m` | Alpaca `1Min`, regular session only |
| `5m` | 300 | Binance `5m` | built from 1m |
| `15m` | 900 | Binance `15m` | built from 1m |
| `1h` | 3600 | Binance `1h` | built from 1m, aligned to the session open |
| `4h` | 14400 | Binance `4h` | built from 1m, two candles per session |
| `1d` | 86400 | Binance `1d` | Alpaca `1Day`, see [4h and 1d](#4h-and-1d) |

## Time

- All times in responses are UTC epoch seconds (integers). Requests accept epoch seconds or
  ISO 8601 dates and date-times (`2024-06-03`, `2024-06-03T13:30:00Z`,
  `2024-06-03T09:30:00-04:00`); a date-time without an offset is UTC, a date is its 00:00
  UTC. In a URL, `+` of an offset must be written as `%2B`.
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
| `1d` | native Binance 1d, 00:00-24:00 UTC | Alpaca `1Day` (IEX), one candle per session, labelled with the session open in UTC |

Stock `1d` is Alpaca's `1Day` bar: on the IEX feed its prices equal the regular-session
aggregate of the 1m bars (checked on 20 days, see [Facts](#facts-verified-against-the-sources)),
and one request returns years of them. Alpaca stamps it 00:00 New York; it is relabelled to the
open of that day's session (2024-06-03 -> `1717421400`, 09:30 EDT), so the 1d label equals the
label of the day's first 1m, 1h and 4h candle. Its volume is 0.01-0.85% higher than the sum of
the 1m volumes: the daily bar counts trades that form no minute bar. On the SIP feed this would
not hold (SIP `1Day` includes extended hours), and 1d would have to be built from 1m.

## What is fetched

A request's period is split into chunks of one instrument and one base timeframe (the requested
timeframe for crypto; 1m, or `1Day` for 1d, for stocks). Each chunk is fetched once, validated
and cached (see [Cache](#cache)); the chunks are joined, resampled for stocks and sliced to
`[start, end)`. Chunk boundaries are UTC calendar days, months and years.

| Chunk | Crypto | Stock |
| --- | --- | --- |
| closed month (1m) or year (1d) | monthly archive; while it is not published yet, built from the daily archives | one request (1m: a month of IEX bars is under 10000) |
| current month or year before today | one chunk per day: daily archive, `GET /api/v3/klines` while it is not published | one chunk for all days so far |
| today up to the request (live tail) | `GET /api/v3/klines` | one request |

**Crypto** (`BINANCE_DATA_URL`, `BINANCE_API_URL`)

| Where from | URL |
| --- | --- |
| monthly archive | `data/spot/monthly/klines/<SYMBOL>/<tf>/<SYMBOL>-<tf>-<YYYY-MM>.zip` |
| daily archive | `data/spot/daily/klines/<SYMBOL>/<tf>/<SYMBOL>-<tf>-<YYYY-MM-DD>.zip` |
| REST | `GET /api/v3/klines?symbol=&interval=&startTime=&endTime=&limit=1000`, paged by 1000 |

- Every archive is verified against its `<file>.CHECKSUM` (SHA-256) before it is read; a 404 of
  the archive or its checksum means "not published yet".
- Archive CSV columns used: open time, open, high, low, close and volume (the first six of 12,
  no header row).
- Open times are microseconds in archives from 2025-01-01 on and milliseconds before (REST is
  always milliseconds); the unit is decided per value (`>= 10^15` is microseconds) and
  converted to seconds. `close_time` is only used to drop the newest REST row while it is still
  open.
- REST `startTime` and `endTime` are both inclusive: a chunk `[start, end)` sends
  `endTime = end - 1 ms`.
- A few archives hold candles that open off the timeframe's UTC grid (see
  [Facts](#binance)). REST has these periods on the grid, so the span from the first to the
  last such candle of an archive is taken from `GET /api/v3/klines` instead.
- `available_from`: `GET /api/v3/klines?interval=1m&startTime=0&limit=1`.

**Stocks** (`ALPACA_DATA_URL`, `ALPACA_API_URL`)

- `GET /v2/stocks/bars` with `feed=iex`, `adjustment=all`, `timeframe=1Min` (or `1Day` for
  1d), `limit=10000`, following `next_page_token`. Alpaca's `end` is inclusive: a chunk
  `[start, end)` sends `end - 1 s`.
- 1m bars outside the sessions of the calendar are dropped before anything is built (IEX has
  sparse pre-market and after-hours prints).
- Unknown symbols are answered with 200 and no bars, so unknown instruments are recognised by
  the catalog, before any bar request.
- `available_from`: the first `1Day` bar from 2016-01-01 (`limit=1`), labelled with its
  session open.

## Gaps

- A gap is an expected candle that the source did not deliver. Expected candles: crypto,
  every aligned bin of the period; stocks, every session bin of the period.
- Gaps are never filled, interpolated or forward-filled. They are reported in `meta.gaps`,
  merged `[start, end)` ranges, earliest first, at most 100, and `meta.gaps_total`, the total
  number of missing candles. Consecutive missing candles form one range, for stocks also
  across a night or weekend; a range ends where its last missing candle ends (at most the
  session close).
- Typical causes: exchange maintenance and trading halts; minutes without any IEX trade
  (common for illiquid stocks at 1m, rare at 1h and above).
- Candles with zero volume are kept as delivered.

## Validation

Requests are checked in this order; the first failure is the answer.

| Check | Error |
| --- | --- |
| client rate limit | 429 `rate-limited` |
| parameters present and well-formed: instrument id, timeframe from the list, `start` and `end` as epoch seconds or ISO 8601, `start < end` | 422 `validation` |
| instrument in the catalog | 404 `instrument-not-found` |
| `start >= available_from` and `end <=` request time | 422 `period-out-of-range` |
| expected candle count `<= CANDLES_MAX` | 422 `too-many-candles` |

Source data is checked before it is cached:

- sorted by time; rows with the same timestamp collapse to one (the last wins)
- open, high, low and close are positive
- `low <= min(open, close)` and `high >= max(open, close)`
- volume is not negative
- timestamps strictly increase
- crypto candles open on the timeframe's UTC grid
- Binance archives match their checksum

Data that fails is not cached, the failure is logged, and the request gets 502
`source-data-invalid`. Its detail names the source and what to do; what failed (the rule, a
parser message) is only in the log.

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
| Clients: `CLIENT_RATE_LIMIT` | client IP (`CF-Connecting-IP`, else the peer address; an IPv6 address counts as its /64 network); every `/candles` and instrument-detail request, cached or not | 60 per minute, `0` disables | 429 `rate-limited` with `Retry-After` |
| Alpaca: `ALPACA_RATE_LIMIT` | environment; each Alpaca request | prod 150, stage 60, `pr-*` 30 | 503 `source-unavailable` with `Retry-After` |
| Binance REST: `BINANCE_WEIGHT_LIMIT` | environment; request weight of each REST call | 1000 | 503 `source-unavailable` with `Retry-After` |
| `data.binance.vision` | not limited | | |

- When our budget at a source is spent, a request waits for the next window if it begins
  within 5 s; otherwise it gets 503 `source-unavailable` with `Retry-After`.
- Alpaca allows 200 requests per minute per key. Prod has its own key; stage and previews
  share one, so stage plus four previews stay within it.
- Intraday stock candles need one Alpaca request per month of 1m bars, so a cold request for
  years of them can need more than a minute's budget. It then gets 503 with `Retry-After`; the
  months fetched so far stay cached and the retry continues from there.
- Binance limits request weight to 6000 per minute per IP, and all environments on the VM
  share one IP. When `X-MBX-USED-WEIGHT-1M` reaches 5000, REST calls pause until the minute
  ends. Weights: `exchangeInfo` 20, `klines` 2 (any `limit`), `ping` 1.
- A 429 from a source is retried with backoff when its `Retry-After` is at most 10 s; when
  retries run out the request gets 503 `source-unavailable`. After a 429 or 418 (IP ban) from
  Binance, REST calls pause for its `Retry-After` (60 s without one).
- When Redis fails, the limits are not counted (requests pass) for 5 s at a time.

## Cache

Redis, per environment, no persistence, `allkeys-lru`: anything can disappear and is fetched
again. Keys:

| Key | Value | Lifetime |
| --- | --- | --- |
| `data:v1:catalog:<market>` | instrument list of the market with its fetch time (compact JSON) | 7 days; refreshed when older than 24 h, the old list is served while one background task refreshes it |
| `data:v1:calendar` | NYSE sessions from 2016 to the end of next year | 7 days |
| `data:v1:candles:<instrument>:<base timeframe>:<chunk>` | one chunk of validated candles, Arrow IPC + zstd | see below |
| `data:v1:first:<instrument>` | `available_from` | 7 days; 1 hour while the instrument has no candle |
| `data:v1:health:<source>` | reachability of the source | 60 s |
| `data:lock:<key without data:v1:>` | single-flight lock for a key being fetched | 30 s |
| `data:fail:<key without data:v1:>` | the error of a failed fetch of that key (source unavailable or invalid data) | 10 s, or the error's `Retry-After` when shorter |
| `data:rl:client:<ip>:<minute>`, `data:rl:alpaca:<minute>`, `data:rl:binance:<minute>` | fixed-window counters; `<ip>` is an IPv4 address or an IPv6 /64 network, `<minute>` is Unix time // 60 | 61 s |

| Chunk | `<chunk>` | Crypto | Stock |
| --- | --- | --- | --- |
| closed month or year | `2024-06`, `2024` | 30 days | 1 day |
| closed day of the current month | `2026-09-25` | 7 days | |
| current month or year before today | `2026-09-01..2026-09-26` (end exclusive) | | 1 day |
| today up to the request | `2026-09-26-live` | 60 s | 60 s |

- Stock chunks live one day because `adjustment=all` rewrites past bars after every dividend or
  split.
- A chunk starts with its complete-until time (8 bytes) before the Arrow data. Candles that
  closed after the live chunk was fetched are neither returned nor reported as gaps until the
  chunk is fetched again.
- Single-flight: the first request for a missing key takes the lock (`SET NX`), fetches and
  stores the value; concurrent requests for the same key, in any process, wait for the value
  instead of calling the source again. When the fetch fails, its error is kept for 10 s: the
  waiting requests and new ones get the same 502 or 503 at once, without calling the source.
- The catalogs are also kept in process memory for search (about 15k instruments, a search takes
  a few ms). A process whose copy is older than 24 h first adopts a newer list from Redis.
- When Redis fails, values are fetched from the source and not cached for 5 s at a time; a
  Redis failure never fails a request by itself.
- `v1` changes when a value format changes, because Redis keeps its contents across deploys.
- `GET /api/health/sources` reports `ok` or `error` per source (Binance `GET /api/v3/ping`,
  Alpaca `GET /v2/clock`) from the 60 s health keys.

## Candles endpoint

`GET /api/v1/data/candles?instrument=<id>&timeframe=<tf>&start=<time>&end=<time>`

| Parameter | Rule |
| --- | --- |
| `instrument` | required, an instrument id |
| `timeframe` | required, one of `1m 5m 15m 1h 4h 1d` |
| `start` | required, inclusive; epoch seconds or ISO 8601 (see [Time](#time)) |
| `end` | optional, exclusive, same formats; default the request time |

Example: `/api/v1/data/candles?instrument=stock:AAPL&timeframe=1h&start=2024-06-03&end=2024-06-04`
returns the 7 candles of that session.

Processing: rate limit, validation, catalog lookup, period and count checks, then each chunk
of the period from the cache or the source (single-flight; up to 16 at once for crypto, 4 for
stocks), resampled (stocks) a year of chunks at a time so that years of 1m bars are never held
at once, concatenated, closed candles only, sliced to `[start, end)`, gaps found, fingerprint
computed.

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
    "gaps": [[1717207200, 1717210800]],
    "gaps_total": 1
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
| `meta.gaps` | up to 100 `[start, end)` ranges of missing candles, earliest first |
| `meta.gaps_total` | number of missing candles in total |
| `t` | open times, epoch seconds, strictly increasing |
| `o`, `h`, `l`, `c`, `v` | open, high, low, close, volume as numbers |

## Sources health

`GET /api/health/sources` (not versioned, like `/api/health`) reports whether each source
answers its cheapest request (Binance `GET /api/v3/ping`, Alpaca `GET /v2/clock`), checked at
most once a minute: 200 when both answer, 503 with the same body when one does not.

```json
{
  "status": "ok",
  "sources": {
    "binance": {"status": "ok", "latency_ms": 84, "detail": null},
    "alpaca": {"status": "ok", "latency_ms": 131, "detail": null}
  }
}
```

## Errors

RFC 9457 `application/problem+json`, `type` `https://candlestack.tech/problems/<slug>`. The
`detail` says which limit fired and what to change.

| Status | Slug | When | Extensions |
| --- | --- | --- | --- |
| 404 | `instrument-not-found` | the id is not in the catalog | `instrument` |
| 422 | `validation` | missing or malformed parameters | `errors`: one `{loc, msg, type}` per bad parameter |
| 422 | `period-out-of-range` | `start` before `available_from`, or `end` in the future | `instrument`, `timeframe`, `available_from`, `available_to` |
| 422 | `too-many-candles` | more than `CANDLES_MAX` expected candles | `requested`, `maximum`, `suggestion` (also in `detail`) |
| 429 | `rate-limited` | client over `CLIENT_RATE_LIMIT` | `limit`; header `Retry-After` |
| 502 | `source-data-invalid` | source data failed validation | `source` |
| 503 | `source-unavailable` | source down or timing out, or our budget for it is spent | `source`; header `Retry-After` when waiting helps (our budget is spent, or the source limits us) |

Invalid parameters, all of them at once:

```json
{
  "type": "https://candlestack.tech/problems/validation",
  "title": "Invalid request",
  "status": 422,
  "detail": "query parameter 'timeframe': Input should be '1m', '5m', '15m', '1h', '4h' or '1d'; query parameter 'start': 'yesterday' is neither epoch seconds nor an ISO 8601 date or date-time",
  "errors": [
    {"loc": ["query", "timeframe"], "msg": "Input should be '1m', '5m', '15m', '1h', '4h' or '1d'", "type": "enum"},
    {"loc": ["query", "start"], "msg": "'yesterday' is neither epoch seconds nor an ISO 8601 date or date-time", "type": "time"}
  ]
}
```

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
  "maximum": 50000,
  "suggestion": "Use 5m or a larger timeframe, or end the period at 2024-02-04T17:20:00Z (1707067200) or earlier."
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
  "detail": "More than 60 candle and instrument requests in one minute from this address. Retry in 17 seconds.",
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

Measured on 2026-09-25 (a Friday evening, US market closed): Binance from a developer machine,
Alpaca from a GitHub Actions job with the stage paper keys. The recorded responses the tests
use are in `backend/tests/fixtures/` (see its README).

### Binance

- **Catalog.** `GET /api/v3/exchangeInfo` lists 3713 symbols: 1368 `TRADING`, 2345 `BREAK`.
  Every `TRADING` symbol allows spot trading, so `status` alone selects the catalog.
  `symbolStatus=TRADING&showPermissionSets=false` returns just those in 2.48 MB (53.5 KB
  gzipped) instead of 17.6 MB, at the same weight 20. Quote assets: USDT 496, TRY 310,
  USDC 258, ... Six trading symbols are not ASCII (`币安人生USDT`, `牛来USDT`, ...); REST and
  archives accept them URL-encoded, and responses must be decoded as UTF-8.
- **Archives.** One CSV per zip, no header row, 12 columns, prices and volumes as decimal
  strings. Open times switch from milliseconds to microseconds exactly at 2025-01-01 (monthly
  and daily files). `close_time` is open time + interval - 1 unit. `.CHECKSUM` is
  `<sha256 hex>  <file name>` without a trailing newline; all downloaded archives matched.
  Monthly and daily files hold identical rows, and 1m summed into 1h and 1h into 1d reproduce
  the archives exactly (OHLCV, trades, taker volumes).
- **Archives off the grid.** Scans of the monthly archives (BTCUSDT 1h and 15m and ETHUSDT 1h
  from 2017-08 to 2026-08, BTCUSDT 1m of 2017-12 and 2018-02) found candles whose open time is
  no multiple of the timeframe in two periods: BTCUSDT 1m from 2017-12-04 06:00 to 12-18 10:00
  at `hh:mm:20` (20401 rows), and the two days after the maintenance of 2018-02-08 (from
  2018-02-09T09:28:14Z, 1m to 1h of BTCUSDT, ETHUSDT and BNBUSDT; 1h at `hh:28:14`). 4h and 1d
  are on the grid. REST returns both periods on the grid, with the maintenance as missing
  candles (1h from 2018-02-09T10:00).
- **Publication lag.** A daily archive appears 01:28-03:26 UTC the next day. A monthly archive
  appears 1-7 days after the month, on the following Monday. Until then the days of a closed
  month come from daily archives, and today (and yesterday before its archive) from REST.
- **REST.** `klines` costs weight 2 whatever the `limit`; `limit` above 1000 is cut to 1000;
  `startTime` and `endTime` are both inclusive; the newest row is the candle still in
  progress. The per-IP limit is 6000 weight per minute (`rateLimits`), reported per response in
  `X-MBX-USED-WEIGHT-1M`. Errors are JSON (`{"code":-1121,"msg":"Invalid symbol."}`), and a
  `BREAK` symbol still returns klines.
- **History.** BTCUSDT from 2017-08-17 (first 1m candle 04:00 UTC, first 1d candle 00:00 UTC);
  a pair listed 2026-09-24 has 1d from 00:00 but 1m only from its first trade at 11:00.

### Alpaca

- **Catalog.** `GET /v2/assets?status=active&asset_class=us_equity`: 14,387 assets (ETFs
  included, no ETF flag), 6.49 MB. Tradable and not OTC: 13,199 (NASDAQ 5600, NYSE 2924,
  ARCA 2739, BATS 1646, AMEX 290). Symbols are `A-Z` and `.` (525 with a dot, e.g. `BRK.B`),
  which work unencoded in every endpoint. Stored minimally, both catalogs are about 1.25 MB.
- **Calendar.** Only trading days, `open`/`close` as New York `HH:MM`; early closes 13:00
  (2024-07-03, 2024-11-29, 2024-12-24), special closures absent. 2016 to 2026 is one request
  (2765 days, 357 KB); the calendar is published about three years ahead.
- **Bars.** `t` is the bar open in RFC 3339 UTC; `v` and `n` are integers. `limit` is at most
  10000 and counts across symbols; pages follow `next_page_token`. `end` is inclusive. A month of
  AAPL IEX 1m bars is 7235 bars, one request. 1Hour bars are aligned to the clock, not the
  session open (the 09:00 bar holds 09:30-09:59), so intraday candles are built from 1m bars.
- **IEX 1Day = regular session.** `1Day` is stamped 00:00 New York. Its open, high, low and
  close equal the aggregate of the regular-session 1m bars on 20 of 20 checked days, including
  four days with extended-hours prints and the early close 2024-11-29 (the all-hours aggregate
  matched only 16). Its volume is 0.01-0.85% higher. SIP `1Day` differs: official auction
  prices and extended-hours volume.
- **Coverage.** IEX starts 2020-07-27 (AAPL, MSFT and UUU; SPY has one stray 1-share 1Day
  bar in 2018). IEX volume is about 0.8% of the market, and 1m bars are sparse: on 2024-06-03
  AAPL has 320 of 390 regular minutes, SPY 330, PLBY 4, UUU 1. IEX carries sparse prints
  before 09:30 and after 16:00, so bars are filtered to the calendar's sessions. SIP starts
  2016-01-04 and answers with the paper keys, but paper accounts are entitled to IEX only.
- **Adjustment.** `adjustment=all` divides prices before a split (NVDA 10:1 on 2024-06-10) and
  multiplies volumes, and applies dividend factors to all earlier bars: adjusted history
  changes after every later corporate action.
- **Errors.** An unknown symbol is 200 with no bars (`{"bars":{}}`); `/v2/assets/<symbol>` is
  404. 400 errors are `{"message":...}` (bad timeframe, `limit` above 10000, end before
  start). Missing or wrong keys give **401 as `text/html`** (an nginx page), without rate-limit
  headers.
- **Rate limit.** Every authenticated response carries `X-Ratelimit-Limit: 200`,
  `X-Ratelimit-Remaining` and `X-Ratelimit-Reset`; `Remaining` is not monotonic across
  calls, so our own counter is the budget. Latency is 145-525 ms per bars request, 1.2 s for
  the assets.

### Decisions from the facts

| Question | Decision |
| --- | --- |
| Stock feed | `iex`: the only feed paper accounts are entitled to. History starts 2020-07-27, not 2016 as first planned. |
| Stock 1d | Alpaca `1Day`, relabelled to the session open (see [4h and 1d](#4h-and-1d)). Intraday timeframes from regular-session 1m bars. |
| Early closes | One 4h candle 09:30-13:00 and no second one; the last 1h candle is 12:30-13:00. |
| Binance timestamps | Unit per value (`>= 10^15` is microseconds), label = open time, `close_time` ignored except for the still-open REST row. |
| Binance current period | Closed month: monthly archive, else daily archives. Current month: daily archive per complete day, REST on 404; REST for today. |
| End of range | Both sources treat `end` as inclusive; the adapters send end minus one unit. |
| Stock cache | Closed stock chunks live 1 day (history is rewritten after corporate actions; 30 days for crypto). Stocks are fetched in whole months (1m) or years (1Day) because one request returns them and Alpaca requests are budgeted; per-day chunks would multiply the requests. |
| Unknown instruments | Recognised by the catalog: Alpaca answers 200 with no bars. Error bodies are never assumed to be JSON. |
| Gaps | IEX minutes without trades are gaps like any other, reported as capped ranges and a total. |

Not verified yet: whether Alpaca returns a partial bar for the session in progress (the market
was closed); candles are only returned once their end has passed, so it would not show.

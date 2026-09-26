# Test fixtures

Real source responses, recorded once and committed so the tests need no network and no keys.

| File | What | Recorded |
| --- | --- | --- |
| `alpaca/calendar-2024.json` | Alpaca `GET /v2/calendar?start=2024-01-01&end=2024-12-31`: 252 trading days, early closes 2024-07-03, 11-29 and 12-24 | 2026-09-25 with the stage paper keys, response body unchanged |
| `binance/archive/monthly/BTCUSDT-1h-2024-01.zip` and `.CHECKSUM` | monthly kline archive of data.binance.vision, 744 rows, open times in milliseconds | 2026-09-25 from a developer machine |
| `binance/archive/monthly/BTCUSDT-1h-2025-01.zip` and `.CHECKSUM` | the same for January 2025, open times in microseconds | 2026-09-25 from a developer machine |
| `binance/archive/daily/BTCUSDT-1h-2024-03-10.zip` and `.CHECKSUM` | daily kline archive, 24 rows | 2026-09-25 from a developer machine |
| `binance/rest/exchangeInfo-trading.json` | `GET /api/v3/exchangeInfo?symbolStatus=TRADING&showPermissionSets=false`, symbols cut to BTCUSDT, ETHUSDT, SOLUSDT, ETHBTC and 币安人生USDT | 2026-09-25 from a developer machine, trimmed as described |
| `binance/rest/klines-BTCUSDT-1h-limit5.json` | `GET /api/v3/klines?symbol=BTCUSDT&interval=1h&limit=5` at 2026-09-25T22:42:42Z (1790376162); the last row is the candle still open | 2026-09-25 from a developer machine |
| `alpaca/assets.json` | `GET /v2/assets?status=active&asset_class=us_equity`, cut to AAPL, SPY (ARCA ETF), BRK.B, HEINY (OTC) and MLGO (not tradable) | 2026-09-25 with the stage paper keys, trimmed as described |
| `alpaca/bars-AAPL-1Min-2024-06-03-p0.json`, `-p1.json` | `GET /v2/stocks/bars` AAPL 1Min of 2024-06-03 with `limit=300`: 300 bars and a `next_page_token`, then the last 20 | 2026-09-25 with the stage paper keys |
| `alpaca/bars-AAPL-1Min-2024-11-29.json` | 1Min of the early close 2024-11-29: 209 bars, 09:30-12:59 EST | 2026-09-25 with the stage paper keys |
| `alpaca/bars-AAPL-1Min-2024-03-08-open.json` | 1Min 14:00-15:31 UTC of 2024-03-08: the EST open at 14:30 and a 14:29 print before it | 2026-09-25 with the stage paper keys |
| `alpaca/bars-AAPL-1Day-2024-06.json` | 1Day of June 2024, 19 bars stamped 04:00 UTC (00:00 EDT) | 2026-09-25 with the stage paper keys |
| `alpaca/bars-AAPL-1Day-2024-11-25_12-02.json` | 1Day 2024-11-25 to 12-02 around the early close, stamped 05:00 UTC (00:00 EST) | 2026-09-25 with the stage paper keys |
| `alpaca/bars-AAPL-1Day-earliest.json` | the first AAPL IEX 1Day bar (`limit=1`): 2020-07-27 | 2026-09-25 with the stage paper keys |
| `alpaca/clock.json` | `GET /v2/clock` while the market was closed | 2026-09-25 with the stage paper keys |
| `alpaca/error-no-auth.html` | the 401 of a request without keys: an nginx `text/html` page (line endings normalised to LF) | 2026-09-25 with the stage paper keys |
| `alpaca/error-unknown-symbol-multi.json` | `GET /v2/stocks/bars?symbols=NOTAREALSYM`: 200 with no bars | 2026-09-25 with the stage paper keys |

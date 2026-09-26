# CandleStack

Configurable pipeline for pattern analysis in financial time series.

Team project at the Faculty of Electrical Engineering and Information Technology,
Slovak University of Technology in Bratislava (STU FEI).

## About

CandleStack is a modular experimentation environment for financial time series.
In a web interface the user assembles a full experiment from three interchangeable layers:

1. **Preprocessing and data representation**: Renko, Kagi, time windows, normalization, segmentation.
2. **Model**: upload and run a trained `.keras` model, with input/output shape validation
   against the chosen preprocessing.
3. **Post-processing and decision**: thresholding, smoothing, clustering, holding period,
   position sizing and risk limits, which turn predictions into trading signals.

Every run produces an experiment with a unified set of metrics and visualizations,
so that runs can be compared to find which combination of representation, architecture
and post-processing gives the most stable results.

## Status

In development. The backend foundation and the market data layer (crypto from Binance, US
stocks from Alpaca) run on prod since v0.2.0, with a placeholder page until the real frontend
exists.

## Run locally

```sh
cp .env.example .env    # optional: Alpaca paper keys for US stocks
docker compose up --build
```

The API reference is then at http://localhost:8000/api/v1/docs. Every endpoint there has a
test request panel to try it, for example:

| Try | Request |
| --- | --- |
| search instruments | `GET /api/v1/data/instruments?q=btc` |
| instrument detail | `GET /api/v1/data/instruments/crypto:BTCUSDT` |
| candles | `GET /api/v1/data/candles?instrument=crypto:BTCUSDT&timeframe=1h&start=2024-06-03&end=2024-06-04` |
| sources reachable | `GET /api/health/sources` |

The local stack runs no frontend, so `/` and the logo in the API reference answer 404 there.

### Alpaca keys for US stocks

Crypto needs no keys. US stocks (`stock:AAPL`) need the keys of an Alpaca paper account:

1. Create a free account at https://alpaca.markets and open its Paper account.
2. Generate an API key there.
3. Put the key ID and the secret into `.env` as `ALPACA_KEY_ID` and `ALPACA_SECRET_KEY`, then
   run `docker compose up --build` again.

Use your own paper account, never the team's. Paper accounts get the IEX feed only, which is
the feed CandleStack uses. Without keys, `/api/health/sources` answers 503 with Alpaca's
`status` `error`, instrument searches report `"unavailable": ["stock"]` and stock requests get
503 `source-unavailable`.

More: [architecture](docs/architecture.md), [market data](docs/data.md),
[contributing](CONTRIBUTING.md), [infrastructure](infra/README.md).

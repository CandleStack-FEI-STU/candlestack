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

In development: the backend foundation, then the market data layer (crypto from Binance,
US stocks from Alpaca).

## Run locally

```sh
cp .env.example .env    # optional: Alpaca paper keys for US stocks
docker compose -f compose.dev.yaml up --build
```

The API reference is then at http://localhost:8000/api/v1/docs. Every endpoint there has a
test request panel to try it, for example:

| Try | Request |
| --- | --- |
| search instruments | `GET /api/v1/data/instruments?q=btc` |
| instrument detail | `GET /api/v1/data/instruments/crypto:BTCUSDT` |
| candles | `GET /api/v1/data/candles?instrument=crypto:BTCUSDT&timeframe=1h&start=2024-06-03&end=2024-06-04` |
| sources reachable | `GET /api/health/sources` |

Crypto needs no keys; US stocks (`stock:AAPL`) need Alpaca paper keys in `.env`.

More: [architecture](docs/architecture.md), [market data](docs/data.md),
[contributing](CONTRIBUTING.md), [infrastructure](infra/README.md).

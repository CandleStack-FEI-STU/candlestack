# Optional features

Ideas beyond the assignment ([assignment.md](assignment.md)) that we may build once the core
pipeline works. None of them is planned yet. Each becomes an issue when we decide to build it.

## CandleStack MCP server for Claude and ChatGPT

A full [MCP](https://modelcontextprotocol.io) server: all of CandleStack as a connector for
Claude and ChatGPT, not only the market data. Everything the web app does is a tool: instruments
and candles, uploading a model, choosing the representation and the decision rules, running
backtests, listing and comparing experiments. Instead of clicking through the builder run by
run, the user describes what to try and the assistant runs it and analyzes the results.

- A remote MCP endpoint next to the API, over the same modules the web app uses.
- Not public. Every tool needs a CandleStack account: the assistant signs in through our login
  (OAuth), and only the accounts we let in get access. Each user sees only their own models and
  experiments.
- Alpaca's terms on its US stock data (personal, noncommercial use, written consent to show it
  to others) apply here as they do to the web app.

## Instrument type filter (stocks and ETFs)

A Type option in Filters that tells stocks from ETFs. Searching for `etf` finds almost every ETF
today (5,345 results, only Netflix by mistake), but misses ETFs without "ETF" in their name such
as QQQ and GLD. Alpaca does not say whether a symbol is an ETF, so the flag would come from a
second source, for example the Nasdaq symbol directory (`nasdaqtraded.txt`, ETF Y/N).

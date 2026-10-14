# Optional features

Ideas beyond the assignment ([assignment.md](assignment.md)) that we may build once the core
pipeline works. None of them is planned yet. Each becomes an issue when we decide to build it.

## CandleStack MCP server for Claude and ChatGPT

A full [MCP](https://modelcontextprotocol.io) server, so Claude and ChatGPT can use CandleStack
as a connector: search instruments, read candles, run backtests and compare experiments from a
chat. Instead of clicking through the builder run by run, the user describes what to try and
the assistant runs it and analyzes the results.

- A remote MCP endpoint next to the API, with tools over the same modules the web app uses:
  instruments and candles first, then runs and experiments once they exist.
- Experiments and uploaded models only behind our login (OAuth), each user sees their own.
- Before it is public: Alpaca's terms allow its US stock data for personal, noncommercial use,
  and showing it to others needs their written consent. An assistant that reads it through the
  server shows it to its user.

## Instrument type filter (stocks and ETFs)

A Type option in Filters that tells stocks from ETFs. Searching for `etf` finds almost every ETF
today (5,345 results, only Netflix by mistake), but misses ETFs without "ETF" in their name such
as QQQ and GLD. Alpaca does not say whether a symbol is an ETF, so the flag would come from a
second source, for example the Nasdaq symbol directory (`nasdaqtraded.txt`, ETF Y/N).

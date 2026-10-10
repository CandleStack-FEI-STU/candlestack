import { queryOptions } from '@tanstack/react-query';

import { get } from './client';
import type { Market } from './instruments';
import type { components } from './schema';
import type { Timeframe } from './timeframes';

export type Candles = components['schemas']['CandlesOut'];

// How many candles one page shows: the chart opens with one page, scrolling left adds one more.
export const PAGE_SIZE = 500;

export const TIMEFRAME_SECONDS: Record<Timeframe, number> = {
  '1m': 60,
  '5m': 300,
  '15m': 900,
  '1h': 3600,
  '4h': 14_400,
  '1d': 86_400,
};

// Stocks trade 6.5 hours on about 252 days a year, so PAGE_SIZE candles span far more calendar
// time than PAGE_SIZE timeframes. The window is widened by that ratio (and never shorter than a
// long weekend) and the page keeps its newest PAGE_SIZE candles. Until #108 brings `limit`,
// this is how we ask for "the last N".
const STOCK_INTRADAY_SPREAD = (24 / 6.5) * (365 / 252);
const STOCK_DAILY_SPREAD = 365 / 252;
const LONG_WEEKEND = 4 * 86_400;

export type CandleWindow = { start: number; end: number };

export function candleWindow(market: Market, timeframe: Timeframe, end: number): CandleWindow {
  const span = PAGE_SIZE * TIMEFRAME_SECONDS[timeframe];
  if (market !== 'stock') return { start: end - span, end };
  const spread = timeframe === '1d' ? STOCK_DAILY_SPREAD : STOCK_INTRADAY_SPREAD;
  return { start: end - Math.max(Math.ceil(span * spread), span + LONG_WEEKEND), end };
}

// GET /api/v1/data/candles. Moves to /instruments/{id}/candles with #104: change it here only.
export function getCandles(
  instrument: string,
  timeframe: Timeframe,
  window: CandleWindow,
  signal?: AbortSignal,
): Promise<Candles> {
  const query = new URLSearchParams({
    instrument,
    timeframe,
    start: String(window.start),
    end: String(window.end),
  });
  return get<Candles>(`/v1/data/candles?${query.toString()}`, signal);
}

export type CandlePage = {
  instrument: string;
  market: Market;
  timeframe: Timeframe;
  // History: the page ends here. Without it, the latest page, which ends now.
  end?: number;
  // Latest page only: reach down at least to here, where the older pages begin.
  since?: number;
};

// The window of the latest page, refreshed: the usual page up to now, stretched down to `since`
// so it still touches the history below it however long the tab sat idle.
export function latestWindow(market: Market, timeframe: Timeframe, now: number, since?: number): CandleWindow {
  const window = candleWindow(market, timeframe, now);
  return since === undefined ? window : { start: Math.min(window.start, since), end: now };
}

// One page of candles. Without `end` it is the latest page: it refreshes at most once a minute.
// With `end` it is history, which never changes: it stays cached for the whole visit.
// `since` is left out of the key on purpose: when it is first set it is the oldest candle of
// the cached latest page, so that page is already right; it only widens later refreshes.
export function candlePageQueryOptions({ instrument, market, timeframe, end, since }: CandlePage) {
  return queryOptions({
    queryKey: ['candles', instrument, timeframe, end ?? 'latest'],
    queryFn: ({ signal }) => {
      const window =
        end === undefined
          ? latestWindow(market, timeframe, Math.floor(Date.now() / 1000), since)
          : candleWindow(market, timeframe, end);
      return getCandles(instrument, timeframe, window, signal);
    },
    staleTime: end === undefined ? 60_000 : Infinity,
    gcTime: end === undefined ? 5 * 60_000 : 30 * 60_000,
  });
}

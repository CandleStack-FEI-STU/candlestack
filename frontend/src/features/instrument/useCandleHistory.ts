import { useQueries, useQuery, type UseQueryResult } from '@tanstack/react-query';
import { useCallback, useState } from 'react';

import {
  ApiError,
  PAGE_SIZE,
  candleBridgeQueryOptions,
  candlePageQueryOptions,
  type Candles,
  type InstrumentDetail,
  type Timeframe,
} from '@/api';

import { bridgeTo, hasOlder, mergePages, type Bar, type History } from './bars';

export type CandleHistory = {
  bars: Bar[];
  gapsTotal: number;
  // The latest page has not arrived yet: nothing to draw.
  isPending: boolean;
  // An older page is on its way; scrolling further left waits for it.
  isLoadingOlder: boolean;
  hasOlder: boolean;
  // How often history started over (see `tooFar`). The chart is keyed by it: a new chart opens
  // on the newest candles, as on the first load, and keeps no view of bars that are gone.
  restarts: number;
  error: Error | null;
  // When that error came: a new one restarts the Retry-After countdown.
  errorAt: number;
  // Retries started by the page itself since the last time everything loaded.
  autoRetries: number;
  loadOlder: () => void;
  retry: () => void;
  autoRetry: () => void;
};

type Pages = {
  history: History;
  // Where the next older page ends, once every older page asked for so far has arrived.
  nextEnd: number | undefined;
  // The bridge for the latest page as it is now has arrived, or none is needed.
  ready: boolean;
  // The bridge or an older page is on its way.
  busy: boolean;
  // An older page is on its way (the bridge alone loads without a word).
  olderBusy: boolean;
  failed: UseQueryResult<Candles> | undefined;
  // The gap above the older pages is too big to bridge: more than one answer may hold
  // (`too-many-candles`, weeks away) or more than BRIDGE_CANDLES. History starts over below the
  // latest page.
  tooFar: boolean;
  // When a page last arrived; automatic retries count from there.
  lastSuccess: number;
};

// The most candles a bridge holds before history starts over instead: the bridge is asked
// again, longer, on every refresh of the latest page.
const BRIDGE_CANDLES = 2 * PAGE_SIZE;

function isTooFar(bridge: UseQueryResult<Candles> | undefined): boolean {
  const { data, error } = bridge ?? {};
  if (error instanceof ApiError && error.problem === 'too-many-candles') return true;
  return data !== undefined && data.t.length + data.meta.gaps_total >= BRIDGE_CANDLES;
}

export type Shown = {
  // The latest page as it is now.
  latest: Candles | undefined;
  // The latest page as the chart last showed it: until the bridge to the latest page as it is
  // now arrives, the chart keeps showing that one (with the bridge before), so no hole shows.
  shown: Candles | undefined;
  anchor: number | undefined;
};

// The bridge and the older pages under the latest page. Called by useQueries only when a page
// changes, so `bars` keeps its identity in between and the chart is not redrawn on every render.
export function summarize({ latest, shown, anchor }: Shown, [bridge, ...older]: UseQueryResult<Candles>[]): Pages {
  const ready =
    bridgeTo(anchor, latest) === undefined || (bridge?.data !== undefined && bridge.isPlaceholderData !== true);
  const history = mergePages({
    latest: ready ? latest : (shown ?? latest),
    older: older.map((page) => page.data),
    bridge: bridge?.data,
    anchor,
  });
  const tooFar = isTooFar(bridge);
  const pages = bridge && !tooFar ? [bridge, ...older] : older;
  return {
    history,
    nextEnd: older.every((page) => page.data) ? history.nextEnd : undefined,
    ready,
    busy: pages.some((page) => page.isFetching),
    olderBusy: older.some((page) => page.isFetching),
    failed: pages.find((page) => page.error),
    tooFar,
    lastSuccess: Math.max(0, ...pages.map((page) => page.dataUpdatedAt)),
  };
}

export type Chain = { olderEnds: number[]; restarts: number };

// Starts history over below the latest page, once for the anchor it hung from: asked again for
// the same anchor (the same errored bridge in another render), it changes nothing.
export function restart(chain: Chain, anchor: number): Chain {
  return chain.olderEnds[0] === anchor ? { olderEnds: [], restarts: chain.restarts + 1 } : chain;
}

// Retries the page starts itself, counted since the last page that arrived. A retry clears the
// error of a page without data, so the count cannot live in the error message; tying it to
// `lastSuccess` starts it again after a success without an effect.
function useAutoRetries(lastSuccess: number, retry: () => void) {
  const [retries, setRetries] = useState({ after: 0, count: 0 });
  const count = retries.after === lastSuccess ? retries.count : 0;
  const autoRetry = useCallback(() => {
    setRetries((current) => ({ after: lastSuccess, count: (current.after === lastSuccess ? current.count : 0) + 1 }));
    retry();
  }, [lastSuccess, retry]);
  return { count, autoRetry };
}

type Base = { instrument: string; timeframe: Timeframe; maxCandles: number };

// The latest page, and the bridge and the older pages under it. The older pages hang below the
// anchor, the start of the latest page when the first of them was asked.
function usePages(base: Base, olderEnds: readonly number[]) {
  const latest = useQuery(candlePageQueryOptions(base));
  const [shown, setShown] = useState<Candles | undefined>(undefined);
  const anchor = olderEnds[0];
  const latestData = latest.data;
  const combine = useCallback(
    (pages: UseQueryResult<Candles>[]) => summarize({ latest: latestData, shown, anchor }, pages),
    [latestData, shown, anchor],
  );
  const pages = useQueries({
    queries: [
      candleBridgeQueryOptions({ ...base, start: anchor, end: bridgeTo(anchor, latestData) }),
      ...olderEnds.map((end) => candlePageQueryOptions({ ...base, end })),
    ],
    combine,
  });
  if (pages.ready && shown !== latestData) setShown(latestData);
  return { latest, pages, anchor };
}

// The candles of one instrument and timeframe: the latest page, plus one older page each time
// the user scrolls to the left edge. Every page is its own query, so history is fetched once
// and kept, and only the latest page ever refreshes; the bridge fills what it left behind. The
// caller mounts it anew for another instrument or timeframe (a React key), which starts again
// from the latest page.
export function useCandleHistory(instrument: InstrumentDetail, timeframe: Timeframe): CandleHistory {
  const [{ olderEnds, restarts }, setChain] = useState<Chain>({ olderEnds: [], restarts: 0 });
  const base = { instrument: instrument.id, timeframe, maxCandles: instrument.max_candles };
  const { latest, pages, anchor } = usePages(base, olderEnds);

  const more = hasOlder(pages.history.nextEnd, instrument.available_from);
  const busy = latest.isFetching || pages.busy;
  const failed = latest.error ? latest : pages.failed;
  const { nextEnd } = pages;
  const loadOlder = useCallback(() => {
    if (busy || failed || !more || nextEnd === undefined) return;
    setChain((chain) =>
      chain.olderEnds.includes(nextEnd) ? chain : { ...chain, olderEnds: [...chain.olderEnds, nextEnd] },
    );
  }, [busy, failed, more, nextEnd]);

  // The only way history is thrown away: drop the older pages right away, during this render.
  // The next render has no anchor and no bridge, so this runs once.
  if (pages.tooFar && anchor !== undefined) setChain((chain) => restart(chain, anchor));

  const retry = useCallback(() => void failed?.refetch(), [failed]);
  const auto = useAutoRetries(Math.max(latest.dataUpdatedAt, pages.lastSuccess), retry);

  return {
    bars: pages.history.bars,
    gapsTotal: pages.history.gapsTotal,
    isPending: latest.isPending,
    isLoadingOlder: pages.olderBusy,
    hasOlder: more,
    restarts,
    error: failed?.error ?? null,
    errorAt: failed?.errorUpdatedAt ?? 0,
    autoRetries: auto.count,
    loadOlder,
    retry,
    autoRetry: auto.autoRetry,
  };
}

import { useQueries, useQuery, type UseQueryResult } from '@tanstack/react-query';
import { useCallback, useEffect, useRef, useState } from 'react';

import {
  ApiError,
  candleBridgeQueryOptions,
  candlePageQueryOptions,
  type Candles,
  type InstrumentDetail,
  type Timeframe,
} from '@/api';

import { bridgeTo, hasOlder, mergePages, type Bar, type History, type Pages } from './bars';

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

// What the chart shows of the latest page and the bridge under it.
export type Frame = Pick<Pages, 'latest' | 'bridge'>;

type Summary = {
  history: History;
  // Where the next older page ends, once every older page asked for so far has arrived.
  nextEnd: number | undefined;
  // The bridge for the latest page as it is now has arrived, or none is needed: `frame` is
  // what the chart shows from now on.
  ready: boolean;
  frame: Frame;
  // An older page is on its way. The bridge does not count: the next older page hangs below
  // the anchor, which the bridge does not move.
  busy: boolean;
  failed: UseQueryResult<Candles> | undefined;
  // The bridge cannot close the gap above the older pages: its candles begin above the anchor
  // (weeks away at 1d, a day at 1m), or the API cannot give that period (`too-many-candles`,
  // `period-out-of-range`). History starts over below the latest page.
  tooFar: boolean;
  // When a page last arrived; automatic retries count from there.
  lastSuccess: number;
};

function isTooFar(bridge: UseQueryResult<Candles> | undefined, anchor: number | undefined): boolean {
  const { data, error } = bridge ?? {};
  if (error instanceof ApiError && (error.problem === 'too-many-candles' || error.problem === 'period-out-of-range')) {
    return true;
  }
  return data !== undefined && anchor !== undefined && data.meta.start > anchor;
}

// Whether the latest page needs a bridge, has one that closes the gap, or cannot get one.
function bridgeState(latest: Candles | undefined, bridge: UseQueryResult<Candles> | undefined, anchor?: number) {
  const needed = bridgeTo(anchor, latest) !== undefined;
  const tooFar = needed && isTooFar(bridge, anchor);
  return { needed, tooFar, ready: !needed || (bridge?.data !== undefined && !tooFar) };
}

export type Shown = {
  // The latest page as it is now.
  latest: Candles | undefined;
  // The latest page and the bridge as the chart last showed them: until the bridge to the latest
  // page as it is now arrives (or while it fails), the chart keeps showing those, so no hole
  // shows and the new candles wait.
  shown: Frame;
  anchor: number | undefined;
};

// The bridge and the older pages under the latest page. Called by useQueries only when a page
// changes, so `bars` keeps its identity in between and the chart is not redrawn on every render.
export function summarize({ latest, shown, anchor }: Shown, [bridge, ...older]: UseQueryResult<Candles>[]): Summary {
  const { needed, ready, tooFar } = bridgeState(latest, bridge, anchor);
  const frame = { latest, bridge: needed ? bridge?.data : undefined };
  const kept = ready || shown.latest === undefined ? frame : shown;
  const history = mergePages({ ...kept, older: older.map((page) => page.data), anchor });
  const pages = bridge && !tooFar ? [bridge, ...older] : older;
  return {
    history,
    nextEnd: older.every((page) => page.data) ? history.nextEnd : undefined,
    ready,
    frame,
    busy: older.some((page) => page.isFetching),
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
  // The frame the chart showed last time everything was ready. Kept after each commit, so it
  // never starts a render of its own.
  const shown = useRef<Frame>({ latest: undefined, bridge: undefined });
  const anchor = olderEnds[0];
  const latestData = latest.data;
  const combine = useCallback(
    (pages: UseQueryResult<Candles>[]) => summarize({ latest: latestData, shown: shown.current, anchor }, pages),
    [latestData, anchor],
  );
  const pages = useQueries({
    queries: [
      candleBridgeQueryOptions({ ...base, end: bridgeTo(anchor, latestData) }),
      ...olderEnds.map((end) => candlePageQueryOptions({ ...base, end })),
    ],
    combine,
  });
  const { ready, frame } = pages;
  useEffect(() => {
    if (ready) shown.current = frame;
  }, [ready, frame]);
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
    isLoadingOlder: pages.busy,
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

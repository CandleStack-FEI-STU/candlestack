import { useQueries, type UseQueryResult } from '@tanstack/react-query';
import { useCallback, useState } from 'react';

import { candlePageQueryOptions, type Candles, type InstrumentDetail, type Timeframe } from '@/api';

import { hasOlder, mergePages, type Bar, type History } from './bars';

export type CandleHistory = {
  bars: Bar[];
  gapsTotal: number;
  // The latest page has not arrived yet: nothing to draw.
  isPending: boolean;
  // An older page is on its way; scrolling further left waits for it.
  isLoadingOlder: boolean;
  hasOlder: boolean;
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
  // Where the next older page ends, once every page asked for so far has arrived.
  nextEnd: number | undefined;
  busy: boolean;
  olderBusy: boolean;
  latestPending: boolean;
  failed: UseQueryResult<Candles> | undefined;
  // When a page last arrived; automatic retries count from there.
  lastSuccess: number;
};

// Called by useQueries only when a page changes, so `bars` keeps its identity in between and
// the chart is not redrawn on every render.
function summarize(pages: UseQueryResult<Candles>[], since: number | undefined): Pages {
  const loaded = pages.flatMap((page) => (page.data ? [page.data] : []));
  const history = mergePages(loaded, since);
  return {
    history,
    nextEnd: loaded.length === pages.length ? history.nextEnd : undefined,
    busy: pages.some((page) => page.isFetching),
    olderBusy: pages.slice(1).some((page) => page.isFetching),
    latestPending: pages[0]?.isPending ?? true,
    failed: pages.find((page) => page.error),
    lastSuccess: Math.max(0, ...pages.map((page) => page.dataUpdatedAt)),
  };
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

// The candles of one instrument and timeframe: the latest page, plus one older page each time
// the user scrolls to the left edge. Every page is its own query, so history is fetched once
// and kept, and only the latest page ever refreshes. The caller mounts it anew for another
// instrument or timeframe (a React key), which starts again from the latest page.
export function useCandleHistory(instrument: InstrumentDetail, timeframe: Timeframe): CandleHistory {
  const [olderEnds, setOlderEnds] = useState<number[]>([]);
  // The latest page always reaches down to where the first older page ends.
  const since = olderEnds[0];
  const base = { instrument: instrument.id, market: instrument.market, timeframe };
  const combine = useCallback((pages: UseQueryResult<Candles>[]) => summarize(pages, since), [since]);
  const pages = useQueries({
    queries: [
      candlePageQueryOptions({ ...base, since }),
      ...olderEnds.map((end) => candlePageQueryOptions({ ...base, end })),
    ],
    combine,
  });

  const more = hasOlder(pages.history.nextEnd, instrument.available_from);
  const { nextEnd, busy, failed } = pages;
  const loadOlder = useCallback(() => {
    if (busy || failed || !more || nextEnd === undefined) return;
    setOlderEnds((ends) => (ends.includes(nextEnd) ? ends : [...ends, nextEnd]));
  }, [busy, failed, more, nextEnd]);

  const retry = useCallback(() => void failed?.refetch(), [failed]);
  const auto = useAutoRetries(pages.lastSuccess, retry);

  return {
    bars: pages.history.bars,
    gapsTotal: pages.history.gapsTotal,
    isPending: pages.latestPending,
    isLoadingOlder: pages.olderBusy,
    hasOlder: more,
    error: failed?.error ?? null,
    errorAt: failed?.errorUpdatedAt ?? 0,
    autoRetries: auto.count,
    loadOlder,
    retry,
    autoRetry: auto.autoRetry,
  };
}

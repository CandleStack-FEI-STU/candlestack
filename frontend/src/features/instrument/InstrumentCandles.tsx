import type { InstrumentDetail, Timeframe } from '@/api';

import { CandleChart } from './CandleChart';
import { CandlesError } from './CandlesError';
import { useCandleHistory } from './useCandleHistory';

function Status({
  isLoadingOlder,
  hasOlder,
  gapsTotal,
}: {
  isLoadingOlder: boolean;
  hasOlder: boolean;
  gapsTotal: number;
}) {
  const notes = [
    isLoadingOlder ? 'Loading older candles…' : hasOlder ? 'Scroll left for older candles.' : 'All history is loaded.',
  ];
  // The chart joins sessions, so a hole in the data would not show. Say so.
  if (gapsTotal > 0) notes.push(`${gapsTotal} candles are missing in the source data and the chart skips them.`);
  return <p className="mt-2 text-xs text-muted-foreground">{notes.join(' ')}</p>;
}

// The chart of one instrument at one timeframe, with its loading and error states.
export function InstrumentCandles({ instrument, timeframe }: { instrument: InstrumentDetail; timeframe: Timeframe }) {
  const history = useCandleHistory(instrument, timeframe);

  return (
    <section aria-label={`${instrument.symbol} candles, ${timeframe}`} className="rounded-lg border p-2 sm:p-4">
      {history.error && (
        <div className="mb-3">
          <CandlesError error={history.error} errorAt={history.errorAt} onRetry={history.retry} />
        </div>
      )}
      {history.isPending ? (
        <p className="py-24 text-center text-sm text-muted-foreground">Loading candles…</p>
      ) : history.bars.length === 0 && !history.error ? (
        <p className="py-24 text-center text-sm text-muted-foreground">No candles in this period.</p>
      ) : (
        <CandleChart bars={history.bars} market={instrument.market} onNearLeftEdge={history.loadOlder} />
      )}
      <Status isLoadingOlder={history.isLoadingOlder} hasOlder={history.hasOlder} gapsTotal={history.gapsTotal} />
    </section>
  );
}

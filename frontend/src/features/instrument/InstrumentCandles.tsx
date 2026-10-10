import type { InstrumentDetail, Market, Timeframe } from '@/api';

import { CandleChart } from './CandleChart';
import { CandlesError } from './CandlesError';
import { timeZoneNote } from './time';
import { useCandleHistory } from './useCandleHistory';

// "1 candle is missing …" or "3 candles are missing …".
function gapsNote(count: number): string {
  const missing = count === 1 ? '1 candle is' : `${count} candles are`;
  return `${missing} missing in the source data and the chart skips ${count === 1 ? 'it' : 'them'}.`;
}

function Status({
  market,
  isLoadingOlder,
  hasOlder,
  gapsTotal,
}: {
  market: Market;
  isLoadingOlder: boolean;
  hasOlder: boolean;
  gapsTotal: number;
}) {
  const notes = [
    isLoadingOlder ? 'Loading older candles…' : hasOlder ? 'Scroll left for older candles.' : 'All history is loaded.',
    timeZoneNote(market),
  ];
  // The chart joins sessions, so a hole in the data would not show. Say so.
  if (gapsTotal > 0) notes.push(gapsNote(gapsTotal));
  return <p className="mt-2 text-xs text-muted-foreground">{notes.join(' ')}</p>;
}

function Placeholder({ children }: { children: string }) {
  return <p className="py-24 text-center text-sm text-muted-foreground">{children}</p>;
}

// The chart of one instrument at one timeframe, with its loading and error states. Without any
// candles there is no chart and no status line: a failed first load shows only its error.
export function InstrumentCandles({ instrument, timeframe }: { instrument: InstrumentDetail; timeframe: Timeframe }) {
  const history = useCandleHistory(instrument, timeframe);
  const hasBars = history.bars.length > 0;

  return (
    <section
      aria-label={`${instrument.symbol} candles, ${timeframe}`}
      className="rounded-lg border bg-background p-2 sm:p-4"
    >
      {history.error && (
        <div className="mb-3">
          <CandlesError
            error={history.error}
            errorAt={history.errorAt}
            autoRetries={history.autoRetries}
            onRetry={history.retry}
            onAutoRetry={history.autoRetry}
          />
        </div>
      )}
      {history.isPending && <Placeholder>Loading candles…</Placeholder>}
      {!history.isPending && !hasBars && !history.error && <Placeholder>No candles in this period.</Placeholder>}
      {hasBars && (
        <>
          <CandleChart bars={history.bars} market={instrument.market} onNearLeftEdge={history.loadOlder} />
          <Status
            market={instrument.market}
            isLoadingOlder={history.isLoadingOlder}
            hasOlder={history.hasOlder}
            gapsTotal={history.gapsTotal}
          />
        </>
      )}
    </section>
  );
}

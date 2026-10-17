import { exchangeName, type DateFormat, type InstrumentDetail } from '@/api';
import { InstrumentIcon } from '@/components/InstrumentIcon';
import { formatDate } from '@/lib/dates';

import { chartTimeZone } from './time';

function Fact({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className={className}>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-mono text-sm">{value}</dd>
    </div>
  );
}

// Icon, name, symbol, exchange, source and since when there is data. On a phone the facts fit
// one line: the symbol is shown only to screen readers (on screen it ends the id above the name)
// and the gaps are narrower, so the chart below keeps its room. A long id or name wraps instead of running off the screen.
// The first day is written in the user's date format, as the day it was in the market's zone.
export function InstrumentHeader({ instrument, dateFormat }: { instrument: InstrumentDetail; dateFormat: DateFormat }) {
  const since =
    instrument.available_from === null
      ? 'unknown'
      : formatDate(new Date(instrument.available_from * 1000), {
          timeZone: chartTimeZone(instrument.market),
          dateFormat,
        });

  return (
    <div className="mb-6">
      <div className="flex items-center gap-3.5">
        <InstrumentIcon id={instrument.id} size={64} />
        <div className="min-w-0">
          <p className="font-mono text-sm break-all text-muted-foreground">{instrument.id}</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight break-words">{instrument.name}</h1>
        </div>
      </div>
      <dl className="mt-4 flex flex-wrap gap-x-5 gap-y-3 sm:gap-x-8">
        <Fact label="Symbol" value={instrument.symbol} className="sr-only sm:not-sr-only" />
        <Fact label="Exchange" value={exchangeName(instrument)} />
        <Fact label="Source" value={`${instrument.source} (${instrument.feed})`} />
        <Fact label="Data since" value={since} />
      </dl>
    </div>
  );
}

import { exchangeName, type InstrumentDetail } from '@/api';

import { chartTimeZone, formatDate } from './time';

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-mono text-sm">{value}</dd>
    </div>
  );
}

// Name, symbol, exchange, source and since when there is data.
export function InstrumentHeader({ instrument }: { instrument: InstrumentDetail }) {
  const since =
    instrument.available_from === null
      ? 'unknown'
      : formatDate(instrument.available_from, chartTimeZone(instrument.market));

  return (
    <div className="mb-6">
      <p className="font-mono text-sm text-muted-foreground">{instrument.id}</p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight">{instrument.name}</h1>
      <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-3">
        <Fact label="Symbol" value={instrument.symbol} />
        <Fact label="Exchange" value={exchangeName(instrument)} />
        <Fact label="Source" value={`${instrument.source} (${instrument.feed})`} />
        <Fact label="Data since" value={since} />
      </dl>
    </div>
  );
}

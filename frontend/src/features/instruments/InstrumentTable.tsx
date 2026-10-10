import { Link } from '@tanstack/react-router';

import type { Instrument } from '@/api';

// Crypto pairs have no exchange in the API: they all come from Binance, which is the exchange.
function exchangeOf(instrument: Instrument): string {
  return instrument.exchange ?? (instrument.source === 'binance' ? 'Binance' : '—');
}

const HEAD = 'px-3 py-2 text-left text-xs font-medium text-muted-foreground';
const CELL = 'px-3 py-2.5';

function Row({ instrument }: { instrument: Instrument }) {
  return (
    <tr className="relative border-b last:border-b-0 hover:bg-accent">
      <td className={`${CELL} font-mono`}>
        <Link
          to="/instrument/$id"
          params={{ id: instrument.id }}
          className="outline-none after:absolute after:inset-0 focus-visible:text-primary"
        >
          {instrument.symbol}
        </Link>
      </td>
      <td className={`${CELL} max-w-[16rem] text-muted-foreground`}>
        <span className="block truncate">{instrument.name}</span>
        {/* On a phone the market and exchange columns are hidden: show them under the name. */}
        <span className="block text-xs capitalize sm:hidden">
          {instrument.market} · {exchangeOf(instrument)}
        </span>
      </td>
      <td className={`${CELL} hidden capitalize sm:table-cell`}>{instrument.market}</td>
      <td className={`${CELL} hidden sm:table-cell`}>{exchangeOf(instrument)}</td>
    </tr>
  );
}

// One row per instrument. The symbol is the row's link, stretched over the whole row, so the
// row is one click target and one tab stop.
export function InstrumentTable({ items }: { items: readonly Instrument[] }) {
  return (
    <table className="w-full border-collapse text-sm">
      <thead className="border-b">
        <tr>
          <th scope="col" className={HEAD}>
            Symbol
          </th>
          <th scope="col" className={HEAD}>
            Name
          </th>
          <th scope="col" className={`${HEAD} hidden sm:table-cell`}>
            Market
          </th>
          <th scope="col" className={`${HEAD} hidden sm:table-cell`}>
            Exchange
          </th>
        </tr>
      </thead>
      <tbody>
        {items.map((instrument) => (
          <Row key={instrument.id} instrument={instrument} />
        ))}
      </tbody>
    </table>
  );
}

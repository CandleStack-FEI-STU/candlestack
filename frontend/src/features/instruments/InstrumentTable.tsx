import { Link } from '@tanstack/react-router';

import { exchangeName, type Instrument } from '@/api';
import { InstrumentIcon } from '@/components/InstrumentIcon';

const HEAD = 'px-3 py-2 text-left text-xs font-medium text-muted-foreground';
// 4 px above and below the 32 px icon: a row is 41 px high with its border, as it was without it.
const CELL = 'px-3 py-1';

function Row({ instrument }: { instrument: Instrument }) {
  return (
    <tr className="relative border-b last:border-b-0 hover:bg-accent">
      <td className={CELL}>
        <div className="flex items-center gap-2.5">
          <InstrumentIcon id={instrument.id} size={32} />
          <Link
            to="/instrument/$id"
            params={{ id: instrument.id }}
            className="font-mono outline-none after:absolute after:inset-0 focus-visible:text-primary"
          >
            {instrument.symbol}
          </Link>
        </div>
      </td>
      <td className={`${CELL} max-w-[16rem] text-muted-foreground`}>
        <span className="block truncate">{instrument.name}</span>
        {/* On a phone the market and exchange columns are hidden: show them under the name. */}
        <span className="block text-xs capitalize sm:hidden">
          {instrument.market} · {exchangeName(instrument)}
        </span>
      </td>
      <td className={`${CELL} hidden capitalize sm:table-cell`}>{instrument.market}</td>
      <td className={`${CELL} hidden sm:table-cell`}>{exchangeName(instrument)}</td>
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

import { Link } from '@tanstack/react-router';

import { exchangeName, type Instrument } from '@/api';
import { InstrumentIcon } from '@/components/InstrumentIcon';

const HEAD = 'px-3 py-2 text-left text-xs font-medium text-muted-foreground';
// 4 px above and below the 32 px icon: a row is 41 px high with its border, as it was without it.
const CELL = 'px-3 py-1';

// Text longer than its column is cut short; its title shows it in full.
function Row({ instrument }: { instrument: Instrument }) {
  const where = `${instrument.market} · ${exchangeName(instrument)}`;
  return (
    <tr className="relative border-b last:border-b-0 hover:bg-accent">
      <td className={CELL}>
        <div className="flex items-center gap-2.5">
          <InstrumentIcon id={instrument.id} size={32} />
          <Link
            to="/instrument/$id"
            params={{ id: instrument.id }}
            title={instrument.symbol}
            className="min-w-0 truncate font-mono outline-none after:absolute after:inset-0 focus-visible:text-primary"
          >
            {instrument.symbol}
          </Link>
        </div>
      </td>
      <td className={`${CELL} text-muted-foreground`}>
        <span title={instrument.name} className="block truncate">
          {instrument.name}
        </span>
        {/* On a phone the market and exchange columns are hidden: show them under the name. */}
        <span title={where} className="block truncate text-xs capitalize sm:hidden">
          {where}
        </span>
      </td>
      <td title={instrument.market} className={`${CELL} hidden truncate capitalize sm:table-cell`}>
        {instrument.market}
      </td>
      <td title={exchangeName(instrument)} className={`${CELL} hidden truncate sm:table-cell`}>
        {exchangeName(instrument)}
      </td>
    </tr>
  );
}

// One row per instrument. The symbol is the row's link, stretched over the whole row, so the
// row is one click target and one tab stop. The columns have fixed widths and the name takes
// the rest, so a long name or symbol truncates instead of widening the table past the screen.
// On a phone the symbol gets half the row (up to 11 characters in full); from sm up the symbol,
// market and exchange get 35, 12 and 15 %, from lg up 40, 10 and 12 %, close to the widths the
// first page had before.
export function InstrumentTable({ items }: { items: readonly Instrument[] }) {
  return (
    <table className="w-full table-fixed border-collapse text-sm">
      <thead className="border-b">
        <tr>
          <th scope="col" className={`${HEAD} w-1/2 sm:w-[35%] lg:w-[40%]`}>
            Symbol
          </th>
          <th scope="col" className={HEAD}>
            Name
          </th>
          <th scope="col" className={`${HEAD} hidden w-[12%] sm:table-cell lg:w-[10%]`}>
            Market
          </th>
          <th scope="col" className={`${HEAD} hidden w-[15%] sm:table-cell lg:w-[12%]`}>
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

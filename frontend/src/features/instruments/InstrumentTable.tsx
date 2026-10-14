import { Link } from '@tanstack/react-router';
import { ArrowDown, ArrowUp } from 'lucide-react';
import type { ReactNode } from 'react';

import { exchangeName, type Instrument, type Market } from '@/api';
import { InstrumentIcon } from '@/components/InstrumentIcon';
import { cn } from '@/lib/utils';
import type { ListSort } from '@/routes/instrumentsSearch';

import { changeTone, formatChange, formatPrice, formatSignedChange, formatVolume } from './numbers';
import { sortedColumn, type SortedColumn } from './sorting';

// Phones (below md) show two columns, the symbol and the price; from md the stats get their own
// columns and the name the rest; from lg the type too. Cells have 12 px at the sides (8 px between
// the two columns of a phone), 4 px above and below the 32 px icon: a row is 41 px high.
const HEAD = 'py-2 text-xs font-medium text-muted-foreground';
const CELL = 'py-1';
const PHONE_FIRST = 'pr-2 pl-3 md:px-3';
const PHONE_LAST = 'pr-3 pl-2 md:px-3';
const WIDE = 'hidden px-3 md:table-cell';
const TONES = { up: 'text-up', down: 'text-down', flat: 'text-muted-foreground', none: 'text-muted-foreground' };
const TYPES: Record<Market, string> = { stock: 'Stock', crypto: 'Crypto' };

// The 12 px arrow of the sorted column.
function Arrow({ direction }: { direction: SortedColumn['direction'] }) {
  const Icon = direction === 'descending' ? ArrowDown : ArrowUp;
  return <Icon aria-hidden className="size-3 shrink-0" />;
}

type HeadProps = { className: string; sorted?: SortedColumn['direction'] | undefined; children: ReactNode };

// A column header; the sorted one is ink with its arrow.
function Head({ className, sorted, children }: HeadProps) {
  return (
    <th scope="col" aria-sort={sorted ?? 'none'} className={cn(HEAD, className, sorted && 'text-foreground')}>
      {children}
    </th>
  );
}

// A header's text and arrow on one line, right-aligned in the number columns.
function Label({ right, arrow, children }: { right?: boolean; arrow?: ReactNode; children: ReactNode }) {
  return (
    <span className={cn('flex items-center gap-1 whitespace-nowrap', right && 'justify-end')}>
      <span className="truncate">{children}</span>
      {arrow}
    </span>
  );
}

// The first two headers, which change on a phone: the symbol says when the list is by volume,
// whose column a phone hides, and the price when it is by change ("Price · 24h").
function PhoneHeads({ sorted }: { sorted: SortedColumn }) {
  const { column, direction } = sorted;
  const arrow = <Arrow direction={direction} />;
  return (
    <>
      <Head className={cn(PHONE_FIRST, 'text-left md:w-[168px]')} sorted={column === 'symbol' ? direction : undefined}>
        <span className={cn('md:hidden', column !== 'change' && 'text-foreground')}>
          <Label arrow={column !== 'change' && arrow}>{column === 'volume' ? 'Symbol · by volume' : 'Symbol'}</Label>
        </span>
        <span className="hidden md:block">
          <Label arrow={column === 'symbol' && arrow}>Symbol</Label>
        </span>
      </Head>
      <Head className={cn(PHONE_LAST, 'w-[100px] text-right md:w-[128px]')}>
        <span className={cn('md:hidden', column === 'change' && 'text-foreground')}>
          <Label right arrow={column === 'change' && arrow}>
            {column === 'change' ? 'Price · 24h' : 'Price'}
          </Label>
        </span>
        <span className="hidden md:block">
          <Label right>Price</Label>
        </span>
      </Head>
    </>
  );
}

function Header({ sort }: { sort: ListSort | undefined }) {
  const sorted = sortedColumn(sort);
  const on = (name: SortedColumn['column']) => (sorted.column === name ? sorted.direction : undefined);
  const arrow = (name: SortedColumn['column']) => on(name) && <Arrow direction={sorted.direction} />;
  return (
    <thead className="border-b">
      <tr>
        <PhoneHeads sorted={sorted} />
        <Head className={cn(WIDE, 'w-[104px] text-right')} sorted={on('change')}>
          <Label right arrow={arrow('change')}>
            24h
          </Label>
        </Head>
        <Head className={cn(WIDE, 'w-[112px] text-right')} sorted={on('volume')}>
          <Label right arrow={arrow('volume')}>
            Volume 24h
          </Label>
        </Head>
        <Head className={cn(WIDE, 'text-left')}>Name</Head>
        <Head className="hidden w-[88px] px-3 text-left lg:table-cell">Type</Head>
        <Head className={cn(WIDE, 'w-[104px] text-left')}>Exchange</Head>
      </tr>
    </thead>
  );
}

// The 24 h change after an 8 px triangle that shows its direction, without a sign.
function Change({ change }: { change: number | null }) {
  const tone = changeTone(change);
  return (
    <span className={cn('inline-flex items-center justify-end gap-0.5 font-mono', TONES[tone])}>
      {tone === 'up' && (
        <svg aria-hidden viewBox="0 0 8 8" className="size-2 shrink-0 fill-current">
          <path d="M4 1 7.5 7h-7Z" />
        </svg>
      )}
      {tone === 'down' && (
        <svg aria-hidden viewBox="0 0 8 8" className="size-2 shrink-0 fill-current">
          <path d="M4 7 .5 1h7Z" />
        </svg>
      )}
      {formatChange(change)}
    </span>
  );
}

// The icon and the symbol, the row's link; on a phone "exchange · volume" under it, as the
// exchange and volume columns are hidden there.
function SymbolCell({ instrument, where }: { instrument: Instrument; where: string }) {
  return (
    <td className={cn(CELL, PHONE_FIRST)}>
      <div className="flex items-center gap-2.5">
        <InstrumentIcon id={instrument.id} size={32} />
        <div className="min-w-0">
          <Link
            to="/instrument/$id"
            params={{ id: instrument.id }}
            title={instrument.symbol}
            className="block truncate font-mono leading-[18px] outline-none after:absolute after:inset-0 focus-visible:text-primary md:leading-5"
          >
            {instrument.symbol}
          </Link>
          <span title={where} className="block truncate text-xs leading-[14px] text-muted-foreground md:hidden">
            {where}
          </span>
        </div>
      </div>
    </td>
  );
}

// The price; on a phone the change under it, with its sign.
function PriceCell({ instrument, stats }: { instrument: Instrument; stats: boolean }) {
  return (
    <td className={cn(CELL, PHONE_LAST, 'text-right')}>
      <span className={cn('block truncate font-mono leading-[18px] md:leading-5', !stats && 'text-muted-foreground')}>
        {formatPrice(instrument.price)}
      </span>
      <span
        className={cn(
          'block truncate text-xs leading-[14px] md:hidden',
          stats ? ['font-mono', TONES[changeTone(instrument.change_24h)]] : 'text-muted-foreground',
        )}
      >
        {stats ? formatSignedChange(instrument.change_24h) : 'No stats yet'}
      </span>
    </td>
  );
}

// Text longer than its column is cut short; its title shows it in full. Without stats the price,
// change and volume are a dash (on a phone, "no stats yet").
function Row({ instrument }: { instrument: Instrument }) {
  const exchange = exchangeName(instrument);
  const stats = instrument.price !== null;
  const where = `${exchange} · ${stats ? formatVolume(instrument.volume_24h) : 'no stats yet'}`;
  return (
    <tr className="relative border-b last:border-b-0 hover:bg-accent">
      <SymbolCell instrument={instrument} where={where} />
      <PriceCell instrument={instrument} stats={stats} />
      <td className={cn(CELL, WIDE, 'text-right')}>
        <Change change={instrument.change_24h} />
      </td>
      <td className={cn(CELL, WIDE, 'text-right font-mono', instrument.volume_24h === null && 'text-muted-foreground')}>
        {formatVolume(instrument.volume_24h)}
      </td>
      <td className={cn(CELL, WIDE, 'text-muted-foreground')}>
        <span title={instrument.name} className="block truncate">
          {instrument.name}
        </span>
      </td>
      <td className={cn(CELL, 'hidden truncate px-3 text-muted-foreground lg:table-cell')}>
        {TYPES[instrument.market]}
      </td>
      <td title={exchange} className={cn(CELL, WIDE, 'truncate text-muted-foreground')}>
        {exchange}
      </td>
    </tr>
  );
}

// One row per instrument with its 24 h stats (#184): Symbol 168 | Price 128 | 24h 104 | Volume 24h
// 112 | Name (the rest) | Type 88 | Exchange 104 px. The symbol is the row's link, stretched over
// the whole row, so the row is one click target and one tab stop. The columns have fixed widths
// and the name takes the rest, so long text truncates instead of widening the table past the
// screen: Type shows from lg (1024 px), the stats, name and exchange from md (768 px); a phone
// shows the symbol over "exchange · volume" and the price over the change. The sorted column's
// header is ink with an arrow.
export function InstrumentTable({ items, sort }: { items: readonly Instrument[]; sort?: ListSort | undefined }) {
  return (
    <table className="w-full table-fixed border-collapse text-sm">
      <Header sort={sort} />
      <tbody>
        {items.map((instrument) => (
          <Row key={instrument.id} instrument={instrument} />
        ))}
      </tbody>
    </table>
  );
}

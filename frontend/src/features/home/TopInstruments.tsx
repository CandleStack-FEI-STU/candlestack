import { useQuery } from '@tanstack/react-query';
import { Link } from '@tanstack/react-router';
import type { ReactNode } from 'react';

import { exchangeName, instrumentSearchQueryOptions, type Instrument } from '@/api';
import { InstrumentIcon } from '@/components/InstrumentIcon';
import { MiniCandles, describeListError, emptyMessage } from '@/features/instruments';
import { changeTone, formatChange, formatPrice, formatSignedChange } from '@/lib/numbers';
import { cn } from '@/lib/utils';

// The first page of the list in its default order (no sort: the API's 24 h volume), five long.
const TOP = { q: '', limit: 5, offset: 0 };

// The list's row with fewer columns: Symbol (the rest) | Exchange 96 | 10d 136 | Price 112 | 24h
// 92 px from sm (640 px); a phone shows the symbol, the last 7 candles in 60 px and the price over
// the change in 104 px. Cells have 12 px at the sides and 8 px between the columns of a phone,
// 4 px above and below the 32 px icon: a row is 41 px high, as in the list.
const HEAD = 'overflow-hidden py-2 text-xs font-medium whitespace-nowrap text-muted-foreground';
const CELL = 'py-1';
const FIRST = 'pr-2 pl-3 sm:px-3';
const MIDDLE = 'px-2 sm:px-3';
const PHONE_LAST = 'pr-3 pl-2 sm:px-3';
const WIDE = 'hidden px-3 sm:table-cell';
const TONES = { up: 'text-up', down: 'text-down', flat: 'text-muted-foreground', none: 'text-muted-foreground' };

function Header() {
  return (
    <thead className="border-b">
      <tr>
        <th scope="col" className={cn(HEAD, FIRST, 'text-left')}>
          Symbol
        </th>
        <th scope="col" className={cn(HEAD, WIDE, 'w-[96px] text-left')}>
          Exchange
        </th>
        <th scope="col" className={cn(HEAD, MIDDLE, 'w-[60px] text-left sm:w-[136px]')}>
          <span className="hidden sm:inline">10d</span>
          <span className="sm:hidden">7d</span>
        </th>
        <th scope="col" className={cn(HEAD, PHONE_LAST, 'w-[104px] text-right sm:w-[112px]')}>
          <span className="hidden sm:inline">Price</span>
          <span className="sm:hidden">Price · 24h</span>
        </th>
        <th scope="col" className={cn(HEAD, WIDE, 'w-[92px] text-right')}>
          24h
        </th>
      </tr>
    </thead>
  );
}

// The 24 h change after an 8 px triangle that shows its direction, without a sign, as in the list.
function Change({ change }: { change: number | null }) {
  const tone = changeTone(change);
  return (
    <span className={cn('inline-flex items-center justify-end gap-0.5 font-mono whitespace-nowrap', TONES[tone])}>
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

// The price; on a phone the change under it, with its sign.
function PriceCell({ instrument }: { instrument: Instrument }) {
  const tone = changeTone(instrument.change_24h);
  return (
    <td className={cn(CELL, PHONE_LAST, 'text-right')}>
      <span
        className={cn('block truncate font-mono leading-[18px]', instrument.price === null && 'text-muted-foreground')}
      >
        {formatPrice(instrument.price)}
      </span>
      <span
        className={cn('block truncate text-xs leading-[14px] sm:hidden', TONES[tone], tone !== 'none' && 'font-mono')}
      >
        {formatSignedChange(instrument.change_24h)}
      </span>
    </td>
  );
}

// The icon and the symbol, the row's link, stretched over the whole row as in the list, so the row
// is one click target and one tab stop. The symbol's text lies above the stretched part, so it is
// underlined only under the pointer, as in the design, not whenever the row is. The link tells the
// instrument page that it was opened from home, so that page's back link returns here.
function SymbolCell({ instrument }: { instrument: Instrument }) {
  return (
    <td className={cn(CELL, FIRST)}>
      <div className="flex items-center gap-2.5">
        <InstrumentIcon id={instrument.id} size={32} />
        <Link
          to="/instrument/$id"
          params={{ id: instrument.id }}
          state={{ from: 'home' }}
          title={instrument.symbol}
          className="min-w-0 truncate font-mono leading-[18px] font-medium outline-none after:absolute after:inset-0 focus-visible:text-primary sm:leading-5"
        >
          <span className="relative z-1 underline-offset-3 hover:underline">{instrument.symbol}</span>
        </Link>
      </div>
    </td>
  );
}

function Row({ instrument }: { instrument: Instrument }) {
  const exchange = exchangeName(instrument);
  return (
    <tr className="relative border-b last:border-b-0 hover:bg-accent">
      <SymbolCell instrument={instrument} />
      <td className={cn(CELL, WIDE)}>
        <span title={exchange} className="block truncate text-muted-foreground">
          {exchange}
        </span>
      </td>
      <td className={cn(CELL, MIDDLE)}>
        <MiniCandles
          id={instrument.id}
          spark={instrument.spark}
          count={10}
          width={112}
          height={32}
          className="hidden sm:block"
        />
        <MiniCandles
          id={instrument.id}
          spark={instrument.spark}
          count={7}
          width={44}
          height={24}
          className="sm:hidden"
        />
      </td>
      <PriceCell instrument={instrument} />
      <td className={cn(CELL, WIDE, 'text-right')}>
        <Change change={instrument.change_24h} />
      </td>
    </tr>
  );
}

// A 9 px bar in place of a text, like the faint sketches of the "Coming soon" sections.
function Ghost({ className }: { className: string }) {
  return <span className={cn('block h-[9px] rounded-[5px] bg-foreground/9', className)} />;
}

// A row while the instruments load: the same cells and height, so nothing moves when they arrive.
function GhostRow() {
  return (
    <tr className="border-b last:border-b-0">
      <td className={cn(CELL, FIRST)}>
        <div className="flex items-center gap-2.5">
          <span className="block size-8 shrink-0 rounded-[10%] bg-foreground/9" />
          <Ghost className="w-16" />
        </div>
      </td>
      <td className={cn(CELL, WIDE)}>
        <Ghost className="w-12" />
      </td>
      <td className={cn(CELL, MIDDLE)}>
        <Ghost className="w-11 sm:w-28" />
      </td>
      <td className={cn(CELL, PHONE_LAST)}>
        <Ghost className="ml-auto w-16" />
      </td>
      <td className={cn(CELL, WIDE)}>
        <Ghost className="ml-auto w-12" />
      </td>
    </tr>
  );
}

// While loading, the table is only a picture: screen readers get the text above it instead.
function Table({ loading, children }: { loading?: boolean; children: ReactNode }) {
  return (
    <table aria-hidden={loading} className="w-full table-fixed border-collapse text-sm">
      <Header />
      <tbody>{children}</tbody>
    </table>
  );
}

function Note({ children, tone = 'muted' }: { children: string; tone?: 'muted' | 'error' }) {
  const color = tone === 'error' ? 'text-destructive' : 'text-muted-foreground';
  return <p className={`px-3 py-12 text-center text-sm ${color}`}>{children}</p>;
}

// The body of the box: the rows once they are here (also when a later refresh fails), the error
// in one line, or ghost rows while they load.
function Body() {
  const result = useQuery(instrumentSearchQueryOptions(TOP));
  if (result.data) {
    const { items } = result.data;
    if (items.length === 0) return <Note>{emptyMessage('', undefined)}</Note>;
    return (
      <Table>
        {items.map((instrument) => (
          <Row key={instrument.id} instrument={instrument} />
        ))}
      </Table>
    );
  }
  // Only the title: the list's hints talk about a search, and the home page has none.
  if (result.isError) return <Note tone="error">{describeListError(result.error, '').title}</Note>;
  return (
    <>
      <p className="sr-only">Loading instruments…</p>
      <Table loading>
        {/* The ghost rows never move: the index is their key. */}
        {Array.from({ length: TOP.limit }, (_, index) => (
          <GhostRow key={index} />
        ))}
      </Table>
    </>
  );
}

// The five most traded instruments on the home page (#199): the instrument list's rows with fewer
// columns, in a box with a solid background, so the page's grid does not show through.
export function TopInstruments() {
  return (
    <div className="overflow-x-auto rounded-lg border bg-background">
      <Body />
    </div>
  );
}

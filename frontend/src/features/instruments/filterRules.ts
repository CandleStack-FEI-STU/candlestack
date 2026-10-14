import { EXCHANGES, exchangeLabel, exchangeMarket, type Exchange, type Market } from '@/api';
import type { InstrumentsSearch, ListSort } from '@/routes/instrumentsSearch';

import { MARKET_NAMES } from './messages';
import { LIST_SORTS, sortLabel } from './sorting';

// The rules of the Filters panel (#182, #184): Type (the market), Sort by and Exchange, all in the
// URL.

// A market and an exchange it does not trade on, as an old or hand-edited link can pair them
// (?market=crypto&exchange=NYSE), or undefined when they fit: All has every exchange, and "All
// exchanges" fits every type.
export function mismatchOf(
  market: Market | undefined,
  exchange: Exchange | undefined,
): { market: Market; exchange: Exchange } | undefined {
  if (market === undefined || exchange === undefined || exchangeMarket(exchange) === market) return undefined;
  return { market, exchange };
}

// The Filters button's text: "All instruments", "Stocks", "Stocks · NYSE", "Crypto · Binance",
// or the exchange alone under All ("NYSE"), and an order other than Volume at the end ("Top
// gainers", "Stocks · Top losers").
export function filtersSummary(market: Market | undefined, exchange: Exchange | undefined, sort?: ListSort): string {
  const parts = [
    market && MARKET_NAMES[market].type,
    exchange && exchangeLabel(exchange),
    sort && sortLabel(sort),
  ].filter(Boolean);
  return parts.length === 0 ? 'All instruments' : parts.join(' · ');
}

// A new type keeps an exchange it has and drops one it does not (Stocks + NYSE -> Crypto drops
// NYSE); it never picks one. Like every change of a filter, it starts at page 1.
export function withType(search: InstrumentsSearch, market: Market | undefined): InstrumentsSearch {
  const exchange = mismatchOf(market, search.exchange) ? undefined : search.exchange;
  return { ...search, market, exchange, page: undefined };
}

// Picking an exchange never changes the type: under All, Binance alone narrows the list to the
// crypto pairs.
export function withExchange(search: InstrumentsSearch, exchange: Exchange | undefined): InstrumentsSearch {
  return { ...search, exchange, page: undefined };
}

// Like a filter, a new order starts at page 1.
export function withSort(search: InstrumentsSearch, sort: ListSort | undefined): InstrumentsSearch {
  return { ...search, sort, page: undefined };
}

type TypeOption = { section: 'type'; market: Market | undefined; label: string; selected: boolean };
type SortOption = { section: 'sort'; sort: ListSort | undefined; label: string; selected: boolean };
type ExchangeOption = {
  section: 'exchange';
  exchange: Exchange | undefined;
  label: string;
  selected: boolean;
  // Why the chosen type rules it out ("Stocks only"); undefined when it can be picked.
  reason: string | undefined;
};
export type FilterOption = TypeOption | SortOption | ExchangeOption;

const TYPES: (Market | undefined)[] = [undefined, 'stock', 'crypto'];

// Every entry of the panel in order: the types, the orders, then All exchanges and the exchanges,
// stock exchanges before Binance, like the types. An exchange the type does not have stays in the
// list, disabled with the reason, so the list keeps its shape and says why.
export function filterOptions(
  market: Market | undefined,
  exchange: Exchange | undefined,
  sort?: ListSort,
): FilterOption[] {
  const types = TYPES.map((value): FilterOption => ({
    section: 'type',
    market: value,
    label: value ? MARKET_NAMES[value].type : 'All types',
    selected: value === market,
  }));
  const exchanges = [undefined, ...EXCHANGES].map((value): FilterOption => {
    const ruledOut = mismatchOf(market, value);
    return {
      section: 'exchange',
      exchange: value,
      label: value ? exchangeLabel(value) : 'All exchanges',
      selected: value === exchange,
      reason: ruledOut && `${MARKET_NAMES[exchangeMarket(ruledOut.exchange)].type} only`,
    };
  });
  const sorts = LIST_SORTS.map((each): FilterOption => ({
    section: 'sort',
    sort: each.sort,
    label: each.label,
    selected: each.sort === sort,
  }));
  return [...types, ...sorts, ...exchanges];
}

// Where the panel shows an entry: under Type, under Sort by, or under Exchange first (All
// exchanges), with the stock exchanges or with the crypto exchanges.
export type OptionGroup = 'type' | 'sort' | 'all-exchanges' | Market;

export function optionGroup(option: FilterOption): OptionGroup {
  if (option.section !== 'exchange') return option.section;
  return option.exchange === undefined ? 'all-exchanges' : exchangeMarket(option.exchange);
}

export function canPick(option: FilterOption): boolean {
  return option.section !== 'exchange' || option.reason === undefined;
}

// The URL after picking an entry.
export function applyOption(search: InstrumentsSearch, option: FilterOption): InstrumentsSearch {
  if (option.section === 'type') return withType(search, option.market);
  if (option.section === 'sort') return withSort(search, option.sort);
  return withExchange(search, option.exchange);
}

// Where the focus goes in a section: its chosen entry, or its first one that can be picked.
export function sectionStart(options: readonly FilterOption[], section: FilterOption['section']): number {
  const chosen = options.findIndex((option) => option.section === section && option.selected && canPick(option));
  return chosen >= 0 ? chosen : options.findIndex((option) => option.section === section && canPick(option));
}

// The entry to keep the focus on: `active`, or, when the type has just disabled it, the chosen or
// first usable entry of its section.
export function usableActive(options: readonly FilterOption[], active: number): number {
  const option = options[active];
  if (option && canPick(option)) return active;
  return sectionStart(options, option?.section ?? 'type');
}

// The arrows, Home and End go through both sections, stopping at the ends.
function moveInList(usable: readonly number[], at: number, key: string): number | undefined {
  if (key === 'ArrowDown') return usable[Math.min(at + 1, usable.length - 1)];
  if (key === 'ArrowUp') return usable[Math.max(at - 1, 0)];
  if (key === 'Home') return usable[0];
  if (key === 'End') return usable.at(-1);
  return undefined;
}

// A letter goes to the next entry that starts with it, round the end.
function typeAhead(options: readonly FilterOption[], usable: readonly number[], at: number, key: string) {
  if (key.length !== 1 || key.trim() === '') return undefined;
  const letter = key.toLowerCase();
  const after = [...usable.slice(at + 1), ...usable.slice(0, at + 1)];
  return after.find((index) => options[index]?.label.toLowerCase().startsWith(letter));
}

type Section = FilterOption['section'];

// How the panel lays out its sections: `wide` (from sm up) has Type over Sort by in the left
// column and Exchange on the right; `phone` has Type and Sort by side by side, Exchange below.
export type PanelLayout = 'wide' | 'phone';

// The sections the vertical arrows (and Home and End) go through from a section: its column.
const COLUMNS: Record<PanelLayout, Record<Section, readonly Section[]>> = {
  wide: { type: ['type', 'sort'], sort: ['type', 'sort'], exchange: ['exchange'] },
  phone: { type: ['type', 'exchange'], sort: ['sort', 'exchange'], exchange: ['type', 'exchange'] },
};

// Where ArrowLeft and ArrowRight go from a section: the section on that side, or itself.
const SIDES: Record<PanelLayout, Record<Section, { ArrowLeft: Section; ArrowRight: Section }>> = {
  wide: {
    type: { ArrowLeft: 'type', ArrowRight: 'exchange' },
    sort: { ArrowLeft: 'sort', ArrowRight: 'exchange' },
    exchange: { ArrowLeft: 'type', ArrowRight: 'exchange' },
  },
  phone: {
    type: { ArrowLeft: 'type', ArrowRight: 'sort' },
    sort: { ArrowLeft: 'type', ArrowRight: 'sort' },
    exchange: { ArrowLeft: 'exchange', ArrowRight: 'exchange' },
  },
};

// Which entry gets the focus after a key press, or undefined when the key does not move it. The
// arrows follow the layout: ArrowLeft and ArrowRight go to the section on that side, the others
// move through the column of the entry. Disabled entries are skipped; a letter goes to the next
// entry that starts with it anywhere in the panel.
export function nextActive(
  options: readonly FilterOption[],
  active: number,
  key: string,
  layout: PanelLayout = 'wide',
): number | undefined {
  const section = options[active]?.section ?? 'type';
  if (key === 'ArrowLeft' || key === 'ArrowRight') {
    const to = SIDES[layout][section][key];
    return to === section ? active : sectionStart(options, to);
  }
  const column = COLUMNS[layout][section];
  const inColumn = options.flatMap((option, index) =>
    canPick(option) && column.includes(option.section) ? [index] : [],
  );
  const moved = moveInList(inColumn, Math.max(0, inColumn.indexOf(active)), key);
  if (moved !== undefined) return moved;
  const usable = options.flatMap((option, index) => (canPick(option) ? [index] : []));
  return typeAhead(options, usable, Math.max(0, usable.indexOf(active)), key);
}

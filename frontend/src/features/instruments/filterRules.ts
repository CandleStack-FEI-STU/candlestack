import { EXCHANGES, exchangeLabel, exchangeMarket, type Exchange, type Market } from '@/api';
import type { InstrumentsSearch } from '@/routes/instrumentsSearch';

import { MARKET_NAMES } from './messages';

// The rules of the Filters panel (#182): Type (the market) and Exchange, both in the URL.

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

// Does the type have this exchange?
export function typeHasExchange(market: Market | undefined, exchange: Exchange | undefined): boolean {
  return mismatchOf(market, exchange) === undefined;
}

// The Filters button's text: "All instruments", "Stocks", "Stocks · NYSE", "Crypto · Binance",
// or the exchange alone under All ("NYSE").
export function filtersSummary(market: Market | undefined, exchange: Exchange | undefined): string {
  const parts = [market && MARKET_NAMES[market].type, exchange && exchangeLabel(exchange)].filter(Boolean);
  return parts.length === 0 ? 'All instruments' : parts.join(' · ');
}

// A new type keeps an exchange it has and drops one it does not (Stocks + NYSE -> Crypto drops
// NYSE); it never picks one. Like every change of a filter, it starts at page 1.
export function withType(search: InstrumentsSearch, market: Market | undefined): InstrumentsSearch {
  const exchange = typeHasExchange(market, search.exchange) ? search.exchange : undefined;
  return { ...search, market, exchange, page: undefined };
}

// Picking an exchange never changes the type: under All, Binance alone narrows the list to the
// crypto pairs.
export function withExchange(search: InstrumentsSearch, exchange: Exchange | undefined): InstrumentsSearch {
  return { ...search, exchange, page: undefined };
}

type TypeOption = { section: 'type'; market: Market | undefined; label: string; selected: boolean };
type ExchangeOption = {
  section: 'exchange';
  exchange: Exchange | undefined;
  label: string;
  selected: boolean;
  // Why the chosen type rules it out ("Stocks only"); undefined when it can be picked.
  reason: string | undefined;
};
export type FilterOption = TypeOption | ExchangeOption;

const TYPES: (Market | undefined)[] = [undefined, 'stock', 'crypto'];

// Every entry of the panel in order: the types, then All exchanges and the exchanges, stock
// exchanges before Binance, like the types. An exchange the type does not have stays in the list,
// disabled with the reason, so the list keeps its shape and says why.
export function filterOptions(market: Market | undefined, exchange: Exchange | undefined): FilterOption[] {
  const types = TYPES.map((value): FilterOption => ({
    section: 'type',
    market: value,
    label: value ? MARKET_NAMES[value].type : 'All types',
    selected: value === market,
  }));
  const exchanges = [undefined, ...EXCHANGES].map((value): FilterOption => ({
    section: 'exchange',
    exchange: value,
    label: value ? exchangeLabel(value) : 'All exchanges',
    selected: value === exchange,
    reason: typeHasExchange(market, value) || !value ? undefined : `${MARKET_NAMES[exchangeMarket(value)].type} only`,
  }));
  return [...types, ...exchanges];
}

// Where the panel shows an entry: under Type, or under Exchange first (All exchanges), with the
// stock exchanges or with the crypto exchanges.
export type OptionGroup = 'type' | 'all-exchanges' | Market;

export function optionGroup(option: FilterOption): OptionGroup {
  if (option.section === 'type') return 'type';
  return option.exchange === undefined ? 'all-exchanges' : exchangeMarket(option.exchange);
}

export function canPick(option: FilterOption): boolean {
  return option.section === 'type' || option.reason === undefined;
}

// The URL after picking an entry.
export function applyOption(search: InstrumentsSearch, option: FilterOption): InstrumentsSearch {
  return option.section === 'type' ? withType(search, option.market) : withExchange(search, option.exchange);
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

// Which entry gets the focus after a key press, or undefined when the key does not move it.
// Disabled entries are skipped; ArrowLeft and ArrowRight jump to the other section.
export function nextActive(options: readonly FilterOption[], active: number, key: string): number | undefined {
  if (key === 'ArrowLeft' || key === 'ArrowRight') {
    const section = key === 'ArrowLeft' ? 'type' : 'exchange';
    return options[active]?.section === section ? active : sectionStart(options, section);
  }
  const usable = options.flatMap((option, index) => (canPick(option) ? [index] : []));
  const at = Math.max(0, usable.indexOf(active));
  return moveInList(usable, at, key) ?? typeAhead(options, usable, at, key);
}

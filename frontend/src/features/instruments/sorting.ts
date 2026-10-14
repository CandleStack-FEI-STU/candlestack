import type { InstrumentSort } from '@/api';
import type { ListSort } from '@/routes/instrumentsSearch';

// The orders of the instrument list (#184): how the Filters panel names each, what the URL says
// (?sort=gainers; Volume, the default, is left out) and what the API is asked for.
type Entry = { sort: ListSort | undefined; label: string; api: InstrumentSort };
const VOLUME: Entry = { sort: undefined, label: 'Volume', api: 'volume' };
const SORTS: Entry[] = [
  VOLUME,
  { sort: 'gainers', label: 'Top gainers', api: 'change' },
  { sort: 'losers', label: 'Top losers', api: '-change' },
  { sort: 'symbol', label: 'Symbol', api: 'symbol' },
];

const entry = (sort: ListSort | undefined) => SORTS.find((each) => each.sort === sort) ?? VOLUME;

// Every order in the panel's order, Volume first.
export const LIST_SORTS = SORTS.map(({ sort, label }) => ({ sort, label }));

export function sortLabel(sort: ListSort | undefined): string {
  return entry(sort).label;
}

// The API's sort; undefined for its default, the 24 h volume, so the request stays as before.
export function apiSort(sort: ListSort | undefined): InstrumentSort | undefined {
  return sort === undefined ? undefined : entry(sort).api;
}

// Which column of the table the list is sorted by, and which way the arrow in its header points.
export type SortedColumn = { column: 'symbol' | 'change' | 'volume'; direction: 'ascending' | 'descending' };

export function sortedColumn(sort: ListSort | undefined): SortedColumn {
  if (sort === 'gainers') return { column: 'change', direction: 'descending' };
  if (sort === 'losers') return { column: 'change', direction: 'ascending' };
  if (sort === 'symbol') return { column: 'symbol', direction: 'ascending' };
  return { column: 'volume', direction: 'descending' };
}

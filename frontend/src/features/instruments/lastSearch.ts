import type { InstrumentsSearch } from '@/routes/instrumentsSearch';

// The list page's last query, market and page, so "Instruments" on an instrument page returns to
// the same search. In memory only: after a reload it is the plain list again.
let last: InstrumentsSearch = {};

export function rememberListSearch(search: InstrumentsSearch): void {
  last = search;
}

export function lastListSearch(): InstrumentsSearch {
  return last;
}

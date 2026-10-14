import { describe, expect, it } from 'vitest';

import { LIST_SORTS, apiSort, sortLabel, sortedColumn } from './sorting';

describe('the orders of the list', () => {
  it('are Volume (the default), Top gainers, Top losers and Symbol', () => {
    expect(LIST_SORTS.map(({ label }) => label)).toEqual(['Volume', 'Top gainers', 'Top losers', 'Symbol']);
    expect(LIST_SORTS.map(({ sort }) => sort)).toEqual([undefined, 'gainers', 'losers', 'symbol']);
    expect(sortLabel(undefined)).toBe('Volume');
    expect(sortLabel('losers')).toBe('Top losers');
  });

  it('ask the API for its sort, and for nothing by default', () => {
    expect(apiSort(undefined)).toBeUndefined();
    expect(apiSort('gainers')).toBe('change');
    expect(apiSort('losers')).toBe('-change');
    expect(apiSort('symbol')).toBe('symbol');
  });

  it('name the sorted column and its direction', () => {
    expect(sortedColumn(undefined)).toEqual({ column: 'volume', direction: 'descending' });
    expect(sortedColumn('gainers')).toEqual({ column: 'change', direction: 'descending' });
    expect(sortedColumn('losers')).toEqual({ column: 'change', direction: 'ascending' });
    expect(sortedColumn('symbol')).toEqual({ column: 'symbol', direction: 'ascending' });
  });
});

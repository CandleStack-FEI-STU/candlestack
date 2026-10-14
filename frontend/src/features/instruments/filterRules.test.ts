import { describe, expect, it } from 'vitest';

import type { Exchange, Market } from '@/api';

import {
  applyOption,
  canPick,
  filterOptions,
  filtersSummary,
  mismatchOf,
  nextActive,
  optionGroup,
  sectionStart,
  usableActive,
  withExchange,
  withSort,
  withType,
  type FilterOption,
} from './filterRules';

const STOCK_EXCHANGES: Exchange[] = ['NASDAQ', 'NYSE', 'ARCA', 'AMEX', 'BATS'];

// The entries as "label (reason)", with a check for the chosen ones, e.g. "✓ NYSE".
const show = (options: FilterOption[]) =>
  options.map((option) => {
    const reason = option.section === 'exchange' && option.reason ? ` (${option.reason})` : '';
    return `${option.selected ? '✓ ' : ''}${option.label}${reason}`;
  });

const indexOf = (options: FilterOption[], label: string) => options.findIndex((option) => option.label === label);

describe('mismatchOf', () => {
  it('lets All have every exchange and every type have "All exchanges"', () => {
    for (const exchange of [...STOCK_EXCHANGES, 'BINANCE'] as Exchange[]) {
      expect(mismatchOf(undefined, exchange)).toBeUndefined();
    }
    for (const market of [undefined, 'stock', 'crypto'] as (Market | undefined)[]) {
      expect(mismatchOf(market, undefined)).toBeUndefined();
    }
  });

  it('gives stocks the stock exchanges and crypto Binance, and names a pair that cannot match', () => {
    for (const exchange of STOCK_EXCHANGES) {
      expect(mismatchOf('stock', exchange)).toBeUndefined();
      expect(mismatchOf('crypto', exchange)).toEqual({ market: 'crypto', exchange });
    }
    expect(mismatchOf('crypto', 'BINANCE')).toBeUndefined();
    expect(mismatchOf('stock', 'BINANCE')).toEqual({ market: 'stock', exchange: 'BINANCE' });
  });
});

describe('filtersSummary', () => {
  it('sums up the type and the exchange', () => {
    expect(filtersSummary(undefined, undefined)).toBe('All instruments');
    expect(filtersSummary('stock', undefined)).toBe('Stocks');
    expect(filtersSummary('crypto', undefined)).toBe('Crypto');
    expect(filtersSummary('stock', 'NYSE')).toBe('Stocks · NYSE');
    expect(filtersSummary('crypto', 'BINANCE')).toBe('Crypto · Binance');
    expect(filtersSummary(undefined, 'NASDAQ')).toBe('NASDAQ');
    expect(filtersSummary(undefined, 'BINANCE')).toBe('Binance');
    // an impossible link says what it holds
    expect(filtersSummary('crypto', 'NYSE')).toBe('Crypto · NYSE');
  });

  it('adds an order other than Volume', () => {
    expect(filtersSummary(undefined, undefined, 'gainers')).toBe('Top gainers');
    expect(filtersSummary('stock', undefined, 'losers')).toBe('Stocks · Top losers');
    expect(filtersSummary('stock', 'NYSE', 'symbol')).toBe('Stocks · NYSE · Symbol');
    expect(filtersSummary(undefined, undefined, undefined)).toBe('All instruments');
  });
});

// Tests compare with toEqual, which takes a key holding undefined as missing: the URL leaves
// those out too.
describe('withType', () => {
  it('keeps an exchange the new type has and drops one it does not', () => {
    expect(withType({ market: 'stock', exchange: 'NYSE' }, undefined)).toEqual({ exchange: 'NYSE' });
    expect(withType({ exchange: 'BINANCE' }, 'crypto')).toEqual({ market: 'crypto', exchange: 'BINANCE' });
    expect(withType({ market: 'stock', exchange: 'NYSE' }, 'crypto')).toEqual({ market: 'crypto' });
    expect(withType({ exchange: 'BINANCE' }, 'stock')).toEqual({ market: 'stock' });
  });

  it('keeps the query and starts at page 1', () => {
    expect(withType({ q: 'btc', page: 3 }, 'crypto')).toEqual({ q: 'btc', market: 'crypto' });
  });
});

describe('withExchange', () => {
  it('never changes the type and starts at page 1', () => {
    expect(withExchange({ q: 'a', page: 2 }, 'BINANCE')).toEqual({ q: 'a', exchange: 'BINANCE' });
    expect(withExchange({ market: 'stock', exchange: 'NYSE' }, 'ARCA')).toEqual({ market: 'stock', exchange: 'ARCA' });
    expect(withExchange({ market: 'crypto', exchange: 'NYSE', page: 4 }, undefined)).toEqual({ market: 'crypto' });
  });
});

describe('withSort', () => {
  it('keeps the filters and starts at page 1', () => {
    expect(withSort({ q: 'a', market: 'stock', page: 3 }, 'gainers')).toEqual({
      q: 'a',
      market: 'stock',
      sort: 'gainers',
    });
    expect(withSort({ sort: 'losers', page: 2 }, undefined)).toEqual({});
  });
});

describe('filterOptions', () => {
  it('lists the types, the orders, then All exchanges, the stock exchanges and Binance, with the choice checked', () => {
    expect(show(filterOptions(undefined, undefined))).toEqual([
      '✓ All types',
      'Stocks',
      'Crypto',
      '✓ Volume',
      'Top gainers',
      'Top losers',
      'Symbol',
      '✓ All exchanges',
      'NASDAQ',
      'NYSE',
      'ARCA',
      'AMEX',
      'BATS',
      'Binance',
    ]);
    expect(filterOptions(undefined, undefined).map(optionGroup)).toEqual([
      'type',
      'type',
      'type',
      'sort',
      'sort',
      'sort',
      'sort',
      'all-exchanges',
      'stock',
      'stock',
      'stock',
      'stock',
      'stock',
      'crypto',
    ]);
  });

  it('checks the chosen order', () => {
    expect(show(filterOptions(undefined, undefined, 'losers')).slice(3, 7)).toEqual([
      'Volume',
      'Top gainers',
      '✓ Top losers',
      'Symbol',
    ]);
  });

  it('disables the exchanges the type does not have and says why, without hiding them', () => {
    expect(show(filterOptions('stock', 'NYSE')).slice(7)).toEqual([
      'All exchanges',
      'NASDAQ',
      '✓ NYSE',
      'ARCA',
      'AMEX',
      'BATS',
      'Binance (Crypto only)',
    ]);
    expect(show(filterOptions('crypto', undefined)).slice(7)).toEqual([
      '✓ All exchanges',
      'NASDAQ (Stocks only)',
      'NYSE (Stocks only)',
      'ARCA (Stocks only)',
      'AMEX (Stocks only)',
      'BATS (Stocks only)',
      'Binance',
    ]);
    expect(filterOptions('crypto', undefined).map(canPick)).toEqual([
      true,
      true,
      true,
      true,
      true,
      true,
      true,
      true,
      false,
      false,
      false,
      false,
      false,
      true,
    ]);
  });

  it('shows the exchange of an impossible link as chosen but disabled', () => {
    const options = filterOptions('crypto', 'NYSE');
    expect(show(options)[9]).toBe('✓ NYSE (Stocks only)');
    expect(canPick(options[9] as FilterOption)).toBe(false);
  });
});

describe('applyOption', () => {
  it('picks a type, an order or an exchange', () => {
    const options = filterOptions('stock', 'NYSE', 'gainers');
    const pick = (label: string) =>
      applyOption(
        { market: 'stock', exchange: 'NYSE', sort: 'gainers', page: 2 },
        options[indexOf(options, label)] as FilterOption,
      );
    expect(pick('All types')).toEqual({ exchange: 'NYSE', sort: 'gainers' });
    expect(pick('Crypto')).toEqual({ market: 'crypto', sort: 'gainers' });
    expect(pick('Top losers')).toEqual({ market: 'stock', exchange: 'NYSE', sort: 'losers' });
    expect(pick('Volume')).toEqual({ market: 'stock', exchange: 'NYSE' });
    expect(pick('ARCA')).toEqual({ market: 'stock', exchange: 'ARCA', sort: 'gainers' });
    expect(pick('All exchanges')).toEqual({ market: 'stock', sort: 'gainers' });
  });
});

describe('sectionStart', () => {
  it('starts on the chosen entry of a section, or its first one that can be picked', () => {
    const options = filterOptions('crypto', 'BINANCE');
    expect(sectionStart(options, 'type')).toBe(indexOf(options, 'Crypto'));
    expect(sectionStart(options, 'exchange')).toBe(indexOf(options, 'Binance'));
    expect(sectionStart(filterOptions(undefined, undefined), 'exchange')).toBe(7);
    expect(sectionStart(filterOptions(undefined, undefined), 'sort')).toBe(3);
    expect(sectionStart(filterOptions(undefined, undefined, 'symbol'), 'sort')).toBe(6);
    // the chosen NYSE cannot be picked under Crypto
    expect(sectionStart(filterOptions('crypto', 'NYSE'), 'exchange')).toBe(7);
  });
});

describe('usableActive', () => {
  it('keeps the focus where it is while the entry can be picked', () => {
    const options = filterOptions('crypto', undefined);
    expect(usableActive(options, indexOf(options, 'Crypto'))).toBe(indexOf(options, 'Crypto'));
    expect(usableActive(options, indexOf(options, 'Binance'))).toBe(indexOf(options, 'Binance'));
  });

  it('moves it off an entry the type has just disabled, to the chosen or first usable one', () => {
    // NYSE had the focus under Stocks; Back went to Crypto
    const crypto = filterOptions('crypto', undefined);
    expect(usableActive(crypto, indexOf(crypto, 'NYSE'))).toBe(indexOf(crypto, 'All exchanges'));
    const binance = filterOptions('crypto', 'BINANCE');
    expect(usableActive(binance, indexOf(binance, 'NYSE'))).toBe(indexOf(binance, 'Binance'));
    expect(usableActive(binance, 99)).toBe(indexOf(binance, 'Crypto'));
  });
});

describe('nextActive', () => {
  const all = filterOptions(undefined, undefined);
  const crypto = filterOptions('crypto', undefined);
  const stock = filterOptions('stock', 'NYSE');
  const at = (options: FilterOption[], label: string) => indexOf(options, label);
  const move = (options: FilterOption[], from: string, key: string) => {
    const next = nextActive(options, at(options, from), key);
    return next === undefined ? undefined : options[next]?.label;
  };

  it('moves through the sections with the arrows and stops at the ends', () => {
    expect(move(all, 'All types', 'ArrowDown')).toBe('Stocks');
    expect(move(all, 'Crypto', 'ArrowDown')).toBe('Volume');
    expect(move(all, 'Symbol', 'ArrowDown')).toBe('All exchanges');
    expect(move(all, 'All exchanges', 'ArrowUp')).toBe('Symbol');
    expect(move(all, 'Binance', 'ArrowDown')).toBe('Binance');
    expect(move(all, 'All types', 'ArrowUp')).toBe('All types');
    expect(move(all, 'NYSE', 'Home')).toBe('All types');
    expect(move(all, 'Stocks', 'End')).toBe('Binance');
  });

  it('skips disabled entries', () => {
    expect(move(crypto, 'All exchanges', 'ArrowDown')).toBe('Binance');
    expect(move(crypto, 'Binance', 'ArrowUp')).toBe('All exchanges');
    expect(move(stock, 'BATS', 'ArrowDown')).toBe('BATS');
    expect(move(stock, 'Crypto', 'End')).toBe('BATS');
  });

  it('goes to the previous or next section with ArrowLeft and ArrowRight', () => {
    expect(move(stock, 'All types', 'ArrowRight')).toBe('Volume');
    expect(move(stock, 'Top losers', 'ArrowRight')).toBe('NYSE');
    expect(move(stock, 'ARCA', 'ArrowLeft')).toBe('Volume');
    expect(move(stock, 'Symbol', 'ArrowLeft')).toBe('Stocks');
    expect(move(all, 'Crypto', 'ArrowRight')).toBe('Volume');
    // at the ends it stays
    expect(move(stock, 'ARCA', 'ArrowRight')).toBe('ARCA');
    expect(move(stock, 'Crypto', 'ArrowLeft')).toBe('Crypto');
  });

  it('jumps to the next entry that starts with a typed letter, round the end', () => {
    expect(move(all, 'All types', 'n')).toBe('NASDAQ');
    expect(move(all, 'NASDAQ', 'N')).toBe('NYSE');
    expect(move(all, 'NYSE', 'n')).toBe('NASDAQ');
    expect(move(all, 'Binance', 'c')).toBe('Crypto');
    expect(move(all, 'Stocks', 's')).toBe('Symbol');
    expect(move(all, 'Symbol', 't')).toBe('Top gainers');
    expect(move(all, 'All types', 'a')).toBe('All exchanges');
    // disabled entries are skipped here too
    expect(move(crypto, 'All types', 'n')).toBeUndefined();
    expect(move(all, 'All types', 'z')).toBeUndefined();
  });

  it('leaves other keys alone', () => {
    for (const key of ['Enter', ' ', 'Escape', 'Tab', 'PageDown', 'F5']) {
      expect(nextActive(all, 0, key)).toBeUndefined();
    }
  });
});

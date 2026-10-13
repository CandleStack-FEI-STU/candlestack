import { describe, expect, it } from 'vitest';

import type { Exchange, Market } from '@/api';

import {
  applyOption,
  canPick,
  filterOptions,
  filtersSummary,
  nextActive,
  optionGroup,
  sectionStart,
  typeHasExchange,
  withExchange,
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

describe('typeHasExchange', () => {
  it('lets All have every exchange and every type have "All exchanges"', () => {
    for (const exchange of [...STOCK_EXCHANGES, 'BINANCE'] as Exchange[]) {
      expect(typeHasExchange(undefined, exchange)).toBe(true);
    }
    for (const market of [undefined, 'stock', 'crypto'] as (Market | undefined)[]) {
      expect(typeHasExchange(market, undefined)).toBe(true);
    }
  });

  it('gives stocks the stock exchanges and crypto Binance', () => {
    for (const exchange of STOCK_EXCHANGES) {
      expect(typeHasExchange('stock', exchange)).toBe(true);
      expect(typeHasExchange('crypto', exchange)).toBe(false);
    }
    expect(typeHasExchange('crypto', 'BINANCE')).toBe(true);
    expect(typeHasExchange('stock', 'BINANCE')).toBe(false);
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

describe('filterOptions', () => {
  it('lists the types, then All exchanges, the stock exchanges and Binance, with the choice checked', () => {
    expect(show(filterOptions(undefined, undefined))).toEqual([
      '✓ All types',
      'Stocks',
      'Crypto',
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
      'all-exchanges',
      'stock',
      'stock',
      'stock',
      'stock',
      'stock',
      'crypto',
    ]);
  });

  it('disables the exchanges the type does not have and says why, without hiding them', () => {
    expect(show(filterOptions('stock', 'NYSE')).slice(3)).toEqual([
      'All exchanges',
      'NASDAQ',
      '✓ NYSE',
      'ARCA',
      'AMEX',
      'BATS',
      'Binance (Crypto only)',
    ]);
    expect(show(filterOptions('crypto', undefined)).slice(3)).toEqual([
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
    expect(show(options)[5]).toBe('✓ NYSE (Stocks only)');
    expect(canPick(options[5] as FilterOption)).toBe(false);
  });
});

describe('applyOption', () => {
  it('picks a type or an exchange', () => {
    const options = filterOptions('stock', 'NYSE');
    const pick = (label: string) =>
      applyOption({ market: 'stock', exchange: 'NYSE', page: 2 }, options[indexOf(options, label)] as FilterOption);
    expect(pick('All types')).toEqual({ exchange: 'NYSE' });
    expect(pick('Crypto')).toEqual({ market: 'crypto' });
    expect(pick('ARCA')).toEqual({ market: 'stock', exchange: 'ARCA' });
    expect(pick('All exchanges')).toEqual({ market: 'stock' });
  });
});

describe('sectionStart', () => {
  it('starts on the chosen entry of a section, or its first one that can be picked', () => {
    const options = filterOptions('crypto', 'BINANCE');
    expect(sectionStart(options, 'type')).toBe(indexOf(options, 'Crypto'));
    expect(sectionStart(options, 'exchange')).toBe(indexOf(options, 'Binance'));
    expect(sectionStart(filterOptions(undefined, undefined), 'exchange')).toBe(3);
    // the chosen NYSE cannot be picked under Crypto
    expect(sectionStart(filterOptions('crypto', 'NYSE'), 'exchange')).toBe(3);
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

  it('moves through both sections with the arrows and stops at the ends', () => {
    expect(move(all, 'All types', 'ArrowDown')).toBe('Stocks');
    expect(move(all, 'Crypto', 'ArrowDown')).toBe('All exchanges');
    expect(move(all, 'All exchanges', 'ArrowUp')).toBe('Crypto');
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

  it('jumps between the sections with ArrowLeft and ArrowRight', () => {
    expect(move(stock, 'All types', 'ArrowRight')).toBe('NYSE');
    expect(move(stock, 'ARCA', 'ArrowLeft')).toBe('Stocks');
    expect(move(all, 'Crypto', 'ArrowRight')).toBe('All exchanges');
    // within its section it stays
    expect(move(stock, 'ARCA', 'ArrowRight')).toBe('ARCA');
    expect(move(stock, 'Crypto', 'ArrowLeft')).toBe('Crypto');
  });

  it('jumps to the next entry that starts with a typed letter, round the end', () => {
    expect(move(all, 'All types', 'n')).toBe('NASDAQ');
    expect(move(all, 'NASDAQ', 'N')).toBe('NYSE');
    expect(move(all, 'NYSE', 'n')).toBe('NASDAQ');
    expect(move(all, 'Binance', 'c')).toBe('Crypto');
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

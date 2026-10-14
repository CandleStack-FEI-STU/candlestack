import { describe, expect, it } from 'vitest';

import {
  changeTone,
  formatChange,
  formatCompact,
  formatPrice,
  formatPriceWith,
  formatSignedChange,
  formatVolume,
  priceDecimals,
} from './numbers';

describe('formatPrice', () => {
  it('shows 2 decimals from 10, 4 between 1 and 10 and 4 significant digits below 1', () => {
    expect(formatPrice(83249.35)).toBe('83,249.35');
    expect(formatPrice(10)).toBe('10.00');
    expect(formatPrice(247.8)).toBe('247.80');
    expect(formatPrice(9.99999)).toBe('10.0000');
    expect(formatPrice(1.3662)).toBe('1.3662');
    expect(formatPrice(1)).toBe('1.0000');
    expect(formatPrice(0.08438)).toBe('0.08438');
    expect(formatPrice(0.0000042)).toBe('0.0000042');
    expect(formatPrice(0.123456)).toBe('0.1235');
  });

  it('shows a dash without a price', () => {
    expect(formatPrice(null)).toBe('—');
  });
});

describe('formatVolume', () => {
  it('shows USD with 3 significant digits', () => {
    expect(formatVolume(1258811866)).toBe('$1.26B');
    expect(formatVolume(684765474)).toBe('$685M');
    expect(formatVolume(4100000)).toBe('$4.1M');
    expect(formatVolume(380000)).toBe('$380K');
    expect(formatVolume(62000)).toBe('$62K');
    expect(formatVolume(512)).toBe('$512');
    expect(formatVolume(0)).toBe('$0');
    expect(formatVolume(1.2e12)).toBe('$1.2T');
  });

  it('shows a dash without a volume', () => {
    expect(formatVolume(null)).toBe('—');
  });
});

describe('the 24 h change', () => {
  it('has a tone by what it shows: 0.00 % is flat', () => {
    expect(changeTone(1.51)).toBe('up');
    expect(changeTone(-3.12)).toBe('down');
    expect(changeTone(0)).toBe('flat');
    expect(changeTone(0.004)).toBe('flat');
    expect(changeTone(-0.004)).toBe('flat');
    expect(changeTone(0.005)).toBe('up');
    expect(changeTone(null)).toBe('none');
  });

  it('is written without a sign next to the triangle', () => {
    expect(formatChange(1.51)).toBe('1.51%');
    expect(formatChange(-3.1234)).toBe('3.12%');
    expect(formatChange(0)).toBe('0.00%');
    expect(formatChange(1234.5)).toBe('1,234.50%');
    expect(formatChange(null)).toBe('—');
  });

  it('is written with its sign on phones', () => {
    expect(formatSignedChange(1.51)).toBe('+1.51%');
    expect(formatSignedChange(-0.71)).toBe('−0.71%');
    expect(formatSignedChange(-0.001)).toBe('0.00%');
    expect(formatSignedChange(null)).toBe('—');
  });
});

describe('priceDecimals', () => {
  it('gives 2 from 10, 4 between 1 and 10 and 4 significant digits below 1', () => {
    expect(priceDecimals(82859.12)).toBe(2);
    expect(priceDecimals(10)).toBe(2);
    expect(priceDecimals(9.5)).toBe(4);
    expect(priceDecimals(1)).toBe(4);
    expect(priceDecimals(0.1234)).toBe(4);
    expect(priceDecimals(0.00001234)).toBe(8);
    expect(priceDecimals(1e-12)).toBe(10);
    expect(priceDecimals(0)).toBe(2);
    expect(priceDecimals(Number.NaN)).toBe(2);
  });

  it('writes a price with exactly those decimals, for the legend', () => {
    expect(formatPriceWith(83249.35, 2)).toBe('83,249.35');
    expect(formatPriceWith(0.0000042, 9)).toBe('0.000004200');
    expect(formatPriceWith(1.3, 4)).toBe('1.3000');
  });
});

describe('formatCompact', () => {
  it('keeps 3 significant digits', () => {
    expect(formatCompact(1234567)).toBe('1.23M');
    expect(formatCompact(7.67)).toBe('7.67');
    expect(formatCompact(1000)).toBe('1K');
  });
});

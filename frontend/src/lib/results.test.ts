import { describe, expect, it } from 'vitest';

import { formatCount, formatPercent, formatSharpe, formatWinRate, returnTone } from './results';

describe('formatSharpe', () => {
  it('writes 2 decimals with a real minus sign, an en dash without a value', () => {
    expect(formatSharpe(1.344)).toBe('1.34');
    expect(formatSharpe(-0.18)).toBe('−0.18');
    expect(formatSharpe(0)).toBe('0.00');
    expect(formatSharpe(-0.004)).toBe('0.00');
    expect(formatSharpe(-0.005)).toBe('−0.01');
    expect(formatSharpe(1234.5)).toBe('1,234.50');
    expect(formatSharpe(null)).toBe('–');
  });
});

describe('formatPercent', () => {
  it('writes a fraction as a percentage with its sign and a space', () => {
    expect(formatPercent(0.965)).toBe('+96.5 %');
    expect(formatPercent(-0.241)).toBe('−24.1 %');
    expect(formatPercent(0)).toBe('+0.0 %');
    expect(formatPercent(-0.0004)).toBe('+0.0 %');
    expect(formatPercent(null)).toBe('–');
  });

  it('colours what it writes: up from zero, down below', () => {
    expect(returnTone(0.246)).toBe('up');
    expect(returnTone(0)).toBe('up');
    expect(returnTone(-0.0004)).toBe('up');
    expect(returnTone(-0.001)).toBe('down');
  });
});

describe('formatWinRate', () => {
  it('writes a share without a sign', () => {
    expect(formatWinRate(0.5556)).toBe('55.6 %');
    expect(formatWinRate(null)).toBe('–');
  });
});

describe('formatCount', () => {
  it('groups the thousands', () => {
    expect(formatCount(1712)).toBe('1,712');
    expect(formatCount(48)).toBe('48');
    expect(formatCount(null)).toBe('–');
  });
});

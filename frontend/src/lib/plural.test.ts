import { describe, expect, it } from 'vitest';

import { plural, pluralNoun } from './plural';

describe('plural', () => {
  it('writes a count with the right noun', () => {
    expect(plural(1, 'model')).toBe('1 model');
    expect(plural(0, 'model')).toBe('0 models');
    expect(plural(3, 'backtest')).toBe('3 backtests');
    expect(pluralNoun(1, 'backtest')).toBe('backtest');
    expect(pluralNoun(2, 'backtest')).toBe('backtests');
  });
});

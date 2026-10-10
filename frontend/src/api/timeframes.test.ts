import { describe, expect, it } from 'vitest';

import { DEFAULT_TIMEFRAME, TIMEFRAMES, instrumentTimeframe, parseTimeframe } from './timeframes';

describe('parseTimeframe', () => {
  it('keeps every known timeframe', () => {
    for (const tf of TIMEFRAMES) expect(parseTimeframe(tf)).toBe(tf);
  });

  it('turns anything else into the default', () => {
    for (const value of [undefined, null, '', 'banana', '1H', '30m', 1, ['1h'], { tf: '1h' }]) {
      expect(parseTimeframe(value)).toBe(DEFAULT_TIMEFRAME);
    }
  });
});

describe('instrumentTimeframe', () => {
  it('keeps the timeframe from the URL when the instrument has it', () => {
    expect(instrumentTimeframe('4h', TIMEFRAMES)).toBe('4h');
  });

  it("falls back to the instrument's first timeframe", () => {
    expect(instrumentTimeframe('1m', ['1h', '1d'])).toBe('1h');
  });

  it('keeps the timeframe when the instrument lists none', () => {
    expect(instrumentTimeframe('1h', [])).toBe('1h');
  });
});

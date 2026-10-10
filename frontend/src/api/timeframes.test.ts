import { describe, expect, it } from 'vitest';

import { DEFAULT_TIMEFRAME, TIMEFRAMES, parseTimeframe } from './timeframes';

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

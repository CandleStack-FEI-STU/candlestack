import { describe, expect, it } from 'vitest';

import type { Bar } from './bars';
import { legendFor } from './legend';

const bar = (time: number, open: number, close: number, volume = 1000): Bar => ({
  time,
  open,
  high: Math.max(open, close) + 1,
  low: Math.min(open, close) - 1,
  close,
  volume,
});

const BARS = [bar(1, 100, 110), bar(2, 110, 99, 1_234_567), bar(3, 99, 99)];

describe('chart legend', () => {
  it('shows the newest candle when the cursor is off the candles', () => {
    expect(legendFor(BARS, null, 2)).toEqual({
      open: '99.00',
      high: '100.00',
      low: '98.00',
      close: '99.00',
      change: '0.00%',
      volume: '1K',
      up: true,
    });
    expect(legendFor(BARS, 7, 2)?.close).toBe('99.00');
  });

  it('measures the change from the previous close, and colors by the candle itself', () => {
    const legend = legendFor(BARS, 1, 2);
    expect(legend?.change).toBe('−10.00%');
    expect(legend?.volume).toBe('1.23M');
    expect(legend?.up).toBe(false);
  });

  it('measures the first candle from its own open', () => {
    expect(legendFor(BARS, 0, 2)?.change).toBe('+10.00%');
  });

  it('has nothing to show without candles', () => {
    expect(legendFor([], null, 2)).toBeNull();
  });

  it('writes prices with the given decimals and thousands separators, like the list', () => {
    const legend = legendFor([bar(1, 83000, 83249.35, 12345)], null, 2);
    expect(legend?.close).toBe('83,249.35');
    expect(legend?.volume).toBe('12.3K');
    expect(legendFor([bar(1, 1.3, 1.3662)], null, 4)?.close).toBe('1.3662');
  });
});

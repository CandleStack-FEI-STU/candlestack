import { describe, expect, it } from 'vitest';

import type { Bar } from './bars';
import { formatVolume, legendFor, priceDecimals } from './legend';

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
    expect(legend?.change).toBe('-10.00%');
    expect(legend?.volume).toBe('1.23M');
    expect(legend?.up).toBe(false);
  });

  it('measures the first candle from its own open', () => {
    expect(legendFor(BARS, 0, 2)?.change).toBe('+10.00%');
  });

  it('has nothing to show without candles', () => {
    expect(legendFor([], null, 2)).toBeNull();
  });

  it('gives cheap prices enough decimals', () => {
    expect(priceDecimals(82859.12)).toBe(2);
    expect(priceDecimals(1)).toBe(2);
    expect(priceDecimals(0.1234)).toBe(4);
    expect(priceDecimals(0.00001234)).toBe(8);
    expect(priceDecimals(0)).toBe(2);
    expect(formatVolume(7.67)).toBe('7.67');
  });
});

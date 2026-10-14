import { describe, expect, it } from 'vitest';

import { candlePaths, candlesLabel, dayLabel, type Spark } from './candlePaths';

const DAY = 86_400;
const OCT_4 = 1_759_536_000; // 2025-10-04 00:00 UTC

type Day = [number, number, number, number, number];

// Ten up days opening at 10 → 19 and closing at 11 → 20.
const RISING = Array.from({ length: 10 }, (_, i): Day => [OCT_4 + i * DAY, 10 + i, 11.5 + i, 9.5 + i, 11 + i]);

describe('candlePaths', () => {
  it('draws a 5 px body and a centred 1 px wick per day, scaled to the low and high with 1 px padding', () => {
    // An up day, a missing day, a down day: low 8, high 12 over 30 px.
    const spark: Spark = [[OCT_4, 10, 12, 8, 11], null, [OCT_4 + 2 * DAY, 11, 11.5, 9, 9.5]];
    expect(candlePaths(spark, 10, 112, 32)).toEqual({
      up: 'M5 1h1V31h-1ZM3 9h5V16h-5Z',
      down: 'M28 5h1V24h-1ZM26 9h5V20h-5Z',
      // the slots after the last day stay empty
      days: [spark[0], null, spark[2], null, null, null, null, null, null, null],
    });
  });

  it('leaves a gap for a day without a candle', () => {
    const spark: Spark = RISING.map((day, i) => (i === 4 ? null : day));
    const paths = candlePaths(spark, 10, 112, 32);
    expect(paths?.days[4]).toBeNull();
    // 9 candles: a wick and a body each
    expect(paths?.up.match(/Z/g)).toHaveLength(18);
    expect(paths?.up).not.toMatch(/M50 /); // the 5th slot's wick (x 48, wick 50) is not drawn
  });

  it('keeps the last 7 days in 44 × 24 px with 3 px bodies', () => {
    const paths = candlePaths(RISING, 7, 44, 24);
    expect(paths?.days).toEqual(RISING.slice(-7));
    // the first slot: x round((6.29 - 3) / 2) = 2, the wick at 3, the body 3 px
    expect(paths?.up).toMatch(/^M3 \d+h1V\d+h-1ZM2 \d+h3V\d+h-3Z/);
  });

  it('counts a close at the open as up, and centres a day that never moved', () => {
    const paths = candlePaths([[OCT_4, 5, 5, 5, 5]], 10, 112, 32);
    expect(paths).toEqual(expect.objectContaining({ up: 'M5 16h1V17h-1ZM3 16h5V17h-5Z', down: '' }));
  });

  it('is null without any candle, for the placeholder line', () => {
    expect(candlePaths(null, 10, 112, 32)).toBeNull();
    expect(candlePaths([], 10, 112, 32)).toBeNull();
    expect(candlePaths([null, null], 10, 112, 32)).toBeNull();
    // only days older than the last 7: nothing to draw on a phone
    expect(candlePaths([[OCT_4, 1, 2, 0.5, 1.5], null, null, null, null, null, null, null], 7, 44, 24)).toBeNull();
  });
});

describe('candlesLabel', () => {
  it('says how many days and the change from the first open to the last close', () => {
    expect(candlesLabel(RISING)).toBe('10 daily candles, +100.00%');
    expect(candlesLabel([null, [OCT_4, 20, 21, 9, 10], null])).toBe('3 daily candles, −50.00%');
    expect(candlesLabel([null])).toBe('No chart yet');
  });
});

describe('dayLabel', () => {
  it('writes the UTC date and the close as the list writes prices', () => {
    expect(dayLabel([OCT_4 + 5 * DAY, 81_754.46, 83_528.98, 81_603.52, 82_635.55])).toBe('Oct 9 · close 82,635.55');
    // a stock session opens at 13:30 UTC: still its day
    expect(dayLabel([OCT_4 + 3 * DAY + 13.5 * 3600, 1, 1, 1, 0.08438])).toBe('Oct 7 · close 0.08438');
  });
});

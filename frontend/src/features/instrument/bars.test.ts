import { describe, expect, it } from 'vitest';

import { candles, times } from '@/test/candles';

import { bridgeTo, hasOlder, mergePages, toBars } from './bars';

// Open times of AAPL's 1m candles in `days` regular sessions from Monday 2026-10-12 on
// (13:30 to 20:00 UTC): nights and the weekend have none.
function sessionMinutes(days: number): number[] {
  const monday = Date.UTC(2026, 9, 12, 13, 30) / 1000;
  return Array.from({ length: days }, (_, day) => times(monday + day * 86_400, 390)).flat();
}

const timesOf = (bars: readonly { time: number }[]) => bars.map((bar) => bar.time);

describe('toBars', () => {
  it('turns the columns into one object per candle', () => {
    expect(toBars(candles([10, 20]))).toEqual([
      { time: 10, open: 10.1, high: 10.2, low: 10.3, close: 10.4, volume: 7 },
      { time: 20, open: 20.1, high: 20.2, low: 20.3, close: 20.4, volume: 7 },
    ]);
  });
});

describe('mergePages', () => {
  it('keeps every candle of the latest page and goes on where it begins', () => {
    const history = mergePages({ latest: candles(times(0, 520)), older: [] });
    expect(history.bars).toHaveLength(520);
    expect(history.nextEnd).toBe(0);
  });

  it('puts the older pages before the latest one and goes on where the oldest begins', () => {
    const history = mergePages({
      latest: candles([300, 360]),
      older: [candles([180, 240]), candles([60, 120])],
      anchor: 300,
    });
    expect(timesOf(history.bars)).toEqual([60, 120, 180, 240, 300, 360]);
    expect(history.nextEnd).toBe(60);
  });

  it('fills the hole above the older pages with the bridge after the latest page refreshed (crypto 1m)', () => {
    // History hangs below the anchor. Ten hours later, the refreshed latest page holds the last
    // 500 minutes, which begin 600 minutes above the anchor; the bridge holds those 600.
    const anchor = 1_800_000_000;
    const older = candles(times(anchor - 500 * 60, 500));
    const latest = candles(times(anchor + 600 * 60, 500));
    const end = bridgeTo(anchor, latest);
    expect(end).toBe(anchor + 600 * 60);
    const bridge = candles(times(anchor, 600));
    const history = mergePages({ latest, older: [older], bridge, anchor });
    expect(timesOf(history.bars)).toEqual(times(anchor - 500 * 60, 1600));
    expect(history.nextEnd).toBe(anchor - 500 * 60);
  });

  it('fills the hole of a stock a minute later in the session with one candle (AAPL 1m)', () => {
    const minutes = sessionMinutes(3);
    const k = 600;
    const anchor = minutes[k] ?? 0;
    const older = candles(minutes.slice(k - 500, k));
    // A minute later the last 500 session minutes begin one candle above the anchor.
    const latest = candles(minutes.slice(k + 1, k + 501));
    expect(bridgeTo(anchor, latest)).toBe(minutes[k + 1]);
    const bridge = candles([anchor]);
    const history = mergePages({ latest, older: [older], bridge, anchor });
    expect(timesOf(history.bars)).toEqual(minutes.slice(k - 500, k + 501));
  });

  it('needs no bridge while the latest page still begins at the anchor', () => {
    expect(bridgeTo(300, candles([300, 360]))).toBeUndefined();
    expect(bridgeTo(undefined, candles([300, 360]))).toBeUndefined();
    expect(bridgeTo(300, undefined)).toBeUndefined();
  });

  it('keeps the older pages while the bridge is on its way', () => {
    const history = mergePages({ latest: candles([600, 660]), older: [candles([180, 240])], anchor: 300 });
    expect(timesOf(history.bars)).toEqual([180, 240, 600, 660]);
    expect(history.nextEnd).toBe(180);
  });

  it('steps past one or two older pages without candles, an outage of the source', () => {
    const outage = [candles([], { start: 200, end: 300 }), candles([], { start: 100, end: 200 })];
    const history = mergePages({ latest: candles([300, 360]), older: outage, anchor: 300 });
    expect(history.nextEnd).toBe(100);
    expect(hasOlder(history.nextEnd, 0)).toBe(true);
  });

  it('ends history after three older pages in a row without candles', () => {
    const empty = (start: number) => candles([], { start, end: start + 100 });
    const history = mergePages({ latest: candles([300, 360]), older: [empty(200), empty(100), empty(0)], anchor: 300 });
    expect(history.nextEnd).toBeUndefined();
    expect(hasOlder(history.nextEnd, -1000)).toBe(false);
  });

  it('ends history at an older page that starts where it ends: nothing opens before it', () => {
    const history = mergePages({
      latest: candles([300, 360]),
      older: [candles([], { start: 300, end: 300 })],
      anchor: 300,
    });
    expect(history.nextEnd).toBeUndefined();
  });

  it('waits for the latest page and goes on below the older pages that arrived', () => {
    expect(mergePages({ latest: undefined, older: [candles([180, 240])], anchor: 300 })).toEqual({
      bars: [],
      nextEnd: undefined,
      gapsTotal: 0,
    });
    const history = mergePages({ latest: candles([300]), older: [candles([180, 240]), undefined], anchor: 300 });
    expect(timesOf(history.bars)).toEqual([180, 240, 300]);
    expect(history.nextEnd).toBe(180);
  });

  it('adds up the gaps of every page', () => {
    const history = mergePages({
      latest: candles([600], { gaps: 1 }),
      bridge: candles([400], { gaps: 2 }),
      older: [candles([200], { gaps: 3 })],
      anchor: 300,
    });
    expect(history.gapsTotal).toBe(6);
  });
});

describe('hasOlder', () => {
  it('stops at the first candle the source has, or when it cannot say', () => {
    expect(hasOlder(200, 100)).toBe(true);
    expect(hasOlder(100, 100)).toBe(false);
    expect(hasOlder(50, 100)).toBe(false);
    expect(hasOlder(200, null)).toBe(false);
    expect(hasOlder(undefined, 100)).toBe(false);
  });
});

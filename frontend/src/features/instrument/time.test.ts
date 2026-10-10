import { describe, expect, it } from 'vitest';

import {
  Tick,
  chartTimeZone,
  crosshairFormatter,
  formatDate,
  tickFormatter,
  timeZoneNote,
  viewerTimeZone,
} from './time';

// 2024-06-03 13:30 UTC: the NYSE open in summer time; 2024-01-08 14:30 UTC: the open in winter.
const SUMMER_OPEN = Date.UTC(2024, 5, 3, 13, 30) / 1000;
const WINTER_OPEN = Date.UTC(2024, 0, 8, 14, 30) / 1000;

describe('chart time', () => {
  it('shows stocks in New York time wherever the viewer is, so the session opens at 09:30 all year', () => {
    const ticks = tickFormatter(chartTimeZone('stock', 'Europe/Bratislava'));
    expect(ticks(SUMMER_OPEN, Tick.Time)).toBe('09:30');
    expect(ticks(WINTER_OPEN, Tick.Time)).toBe('09:30');
  });

  it("shows crypto in the viewer's own time, with summer time", () => {
    const ticks = tickFormatter(chartTimeZone('crypto', 'Europe/Bratislava'));
    expect(ticks(SUMMER_OPEN, Tick.Time)).toBe('15:30');
    expect(ticks(WINTER_OPEN, Tick.Time)).toBe('15:30');
  });

  it("takes the viewer's zone from the browser", () => {
    expect(chartTimeZone('crypto')).toBe(viewerTimeZone());
    expect(viewerTimeZone()).not.toBe('');
  });

  it('says under the chart which clock the axis uses', () => {
    expect(timeZoneNote('stock', 'Europe/Bratislava')).toBe('Times are New York time.');
    expect(timeZoneNote('crypto', 'Europe/Bratislava')).toBe('Times are your time (Europe/Bratislava).');
  });

  it('labels years, months and days on the axis', () => {
    const ticks = tickFormatter('UTC');
    expect(ticks(SUMMER_OPEN, Tick.Year)).toBe('2024');
    expect(ticks(SUMMER_OPEN, Tick.Month)).toBe('Jun');
    expect(ticks(SUMMER_OPEN, Tick.Day)).toBe('3 Jun');
  });

  it('gives the crosshair and the header full dates', () => {
    expect(crosshairFormatter('America/New_York')(SUMMER_OPEN)).toBe('3 Jun 2024, 09:30');
    expect(formatDate(SUMMER_OPEN, 'UTC')).toBe('3 Jun 2024');
  });
});

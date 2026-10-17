import { describe, expect, it } from 'vitest';

import { cityOf, dateStyleOf, formatDate, formatShortDay, formatTime, viewerTimeZone, zoneOf } from './dates';

// 2024-10-12 16:05 UTC: 12:05 in New York, 18:05 in Bratislava.
const MOMENT = new Date(Date.UTC(2024, 9, 12, 16, 5));
// 2024-01-04 02:30 UTC: still 3 January in New York.
const LATE = new Date(Date.UTC(2024, 0, 4, 2, 30));

describe('time zones', () => {
  it('turns the setting into a zone: New York, or the browser’s own', () => {
    expect(zoneOf('ny', 'Europe/Bratislava')).toBe('America/New_York');
    expect(zoneOf('local', 'Europe/Bratislava')).toBe('Europe/Bratislava');
    expect(zoneOf('local')).toBe(viewerTimeZone());
  });

  it('names a zone by its city', () => {
    expect(cityOf('Europe/Bratislava')).toBe('Bratislava');
    expect(cityOf('America/New_York')).toBe('New York');
    expect(cityOf('America/Argentina/Buenos_Aires')).toBe('Buenos Aires');
    expect(cityOf('UTC')).toBe('UTC');
  });

  it('gives a visitor the API’s defaults: New York, 12 Oct 2024, 16:05', () => {
    expect(dateStyleOf(undefined, 'Europe/Bratislava')).toEqual({
      timeZone: 'America/New_York',
      dateFormat: 'dmy',
      timeFormat: '24',
    });
    expect(dateStyleOf({ time_zone: 'local', date_format: 'iso', time_format: '12' }, 'Europe/Bratislava')).toEqual({
      timeZone: 'Europe/Bratislava',
      dateFormat: 'iso',
      timeFormat: '12',
    });
  });
});

describe('formatDate', () => {
  it('writes the three formats of Settings', () => {
    expect(formatDate(MOMENT, { timeZone: 'UTC', dateFormat: 'dmy' })).toBe('12 Oct 2024');
    expect(formatDate(MOMENT, { timeZone: 'UTC', dateFormat: 'iso' })).toBe('2024-10-12');
    expect(formatDate(MOMENT, { timeZone: 'UTC', dateFormat: 'dot' })).toBe('12.10.2024');
  });

  it('pads the day and month only where the format does', () => {
    expect(formatDate(LATE, { timeZone: 'UTC', dateFormat: 'dmy' })).toBe('4 Jan 2024');
    expect(formatDate(LATE, { timeZone: 'UTC', dateFormat: 'iso' })).toBe('2024-01-04');
    expect(formatDate(LATE, { timeZone: 'UTC', dateFormat: 'dot' })).toBe('04.01.2024');
  });

  it('takes the day in the zone', () => {
    expect(formatDate(LATE, { timeZone: 'America/New_York', dateFormat: 'iso' })).toBe('2024-01-03');
  });
});

describe('formatShortDay', () => {
  it('writes the day and the month, without padding, in the zone', () => {
    expect(formatShortDay(MOMENT, { timeZone: 'UTC' })).toBe('12 Oct');
    expect(formatShortDay(LATE, { timeZone: 'UTC' })).toBe('4 Jan');
    expect(formatShortDay(LATE, { timeZone: 'America/New_York' })).toBe('3 Jan');
  });
});

describe('formatTime', () => {
  it('writes 24 or 12 hours, in the zone', () => {
    expect(formatTime(MOMENT, { timeZone: 'UTC', timeFormat: '24' })).toBe('16:05');
    expect(formatTime(MOMENT, { timeZone: 'UTC', timeFormat: '12' })).toBe('4:05 PM');
    expect(formatTime(MOMENT, { timeZone: 'America/New_York', timeFormat: '24' })).toBe('12:05');
    expect(formatTime(MOMENT, { timeZone: 'America/New_York', timeFormat: '12' })).toBe('12:05 PM');
    expect(formatTime(MOMENT, { timeZone: 'Europe/Bratislava', timeFormat: '24' })).toBe('18:05');
  });

  it('writes midnight as 00 or 12 AM, with a plain space before AM', () => {
    const midnight = new Date(Date.UTC(2024, 9, 12, 0, 7));
    expect(formatTime(midnight, { timeZone: 'UTC', timeFormat: '24' })).toBe('00:07');
    expect(formatTime(midnight, { timeZone: 'UTC', timeFormat: '12' })).toBe('12:07 AM');
  });
});

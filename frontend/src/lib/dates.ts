import type { Appearance, DateFormat, TimeFormat, TimeZone } from '@/api';

// How the user wants dates and times written (Settings, Appearance), as the API stores it and
// resolved to a zone. Every date the app shows goes through formatDate and formatTime, so a
// change in Settings reaches all of them.

export const NEW_YORK = 'America/New_York';

// The viewer's own zone from the browser, e.g. 'Europe/Bratislava'.
export function viewerTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
}

// The zone of the time zone setting: New York (exchange time) or the browser's own.
export function zoneOf(setting: TimeZone, viewer = viewerTimeZone()): string {
  return setting === 'ny' ? NEW_YORK : viewer;
}

// A zone as people name it: its city, 'Europe/Bratislava' → 'Bratislava', 'America/New_York' →
// 'New York'.
export function cityOf(zone: string): string {
  return (zone.split('/').at(-1) ?? zone).replaceAll('_', ' ');
}

export type DateStyle = { timeZone: string; dateFormat: DateFormat; timeFormat: TimeFormat };

// How dates and times are written, for a place that has its own zone (the chart).
export type DateFormats = Pick<DateStyle, 'dateFormat' | 'timeFormat'>;

// The API's defaults, for a visitor who is not signed in.
const DEFAULT_APPEARANCE = { time_zone: 'ny', date_format: 'dmy', time_format: '24' } as const;

export function dateStyleOf(
  appearance: Pick<Appearance, 'time_zone' | 'date_format' | 'time_format'> = DEFAULT_APPEARANCE,
  viewer = viewerTimeZone(),
): DateStyle {
  return {
    timeZone: zoneOf(appearance.time_zone, viewer),
    dateFormat: appearance.date_format,
    timeFormat: appearance.time_format,
  };
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// Intl.DateTimeFormat is slow to make, so each one is made once and kept by what it formats.
const formats = new Map<string, Intl.DateTimeFormat>();

function partsOf(date: Date, key: string, options: Intl.DateTimeFormatOptions): Record<string, string> {
  let format = formats.get(key);
  if (format === undefined) {
    format = new Intl.DateTimeFormat('en-US', options);
    formats.set(key, format);
  }
  return Object.fromEntries(format.formatToParts(date).map((part) => [part.type, part.value]));
}

// The calendar day of `date` in `timeZone`, as written in a date: '2024', '06', '03'.
export function calendarDay(date: Date, timeZone: string): { year: string; month: string; day: string } {
  const {
    year = '',
    month = '',
    day = '',
  } = partsOf(date, `date ${timeZone}`, {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
  return { year, month, day };
}

// The short name of a month written as in a date: '06' → 'Jun'.
export function monthName(month: string): string {
  return MONTHS[Number(month) - 1] ?? '';
}

// 12 Oct 2024 (dmy), 2024-10-12 (iso) or 12.10.2024 (dot), the day in `timeZone`. Built from the
// parts, not a locale's pattern, so it reads the same in every browser.
export function formatDate(date: Date, { timeZone, dateFormat }: Pick<DateStyle, 'timeZone' | 'dateFormat'>): string {
  const { year, month, day } = calendarDay(date, timeZone);
  if (dateFormat === 'iso') return `${year}-${month}-${day}`;
  if (dateFormat === 'dot') return `${day}.${month}.${year}`;
  return `${Number(day)} ${monthName(month)} ${year}`;
}

// 16:05 (24) or 4:05 PM (12), in `timeZone`. A plain space before AM and PM: newer browsers put a
// narrow one there, which some fonts draw too thin.
export function formatTime(date: Date, { timeZone, timeFormat }: Pick<DateStyle, 'timeZone' | 'timeFormat'>): string {
  const twelve = timeFormat === '12';
  const {
    hour = '',
    minute = '',
    dayPeriod = '',
  } = partsOf(date, `time ${timeFormat} ${timeZone}`, {
    timeZone,
    hour: twelve ? 'numeric' : '2-digit',
    minute: '2-digit',
    hourCycle: twelve ? 'h12' : 'h23',
  });
  return twelve ? `${hour}:${minute} ${dayPeriod}` : `${hour}:${minute}`;
}

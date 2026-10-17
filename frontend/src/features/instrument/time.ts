import type { Market } from '@/api';
import {
  NEW_YORK,
  calendarDay,
  formatDate,
  formatShortDay,
  formatTime,
  monthName,
  viewerTimeZone,
  type DateStyle,
} from '@/lib/dates';

// The chart's zone for a visitor, who has no time zone setting (signed in, the setting decides).
// Stocks trade on New York time (the session opens at 09:30 there all year). Crypto trades around
// the clock with no home exchange, so it shows the viewer's own time. The API sends UTC epoch
// seconds; without a zone the chart would show UTC.
export function marketTimeZone(market: Market, viewer = viewerTimeZone()): string {
  return market === 'stock' ? NEW_YORK : viewer;
}

// Under the chart, so nobody has to guess which clock the axis uses. Any zone but New York is the
// viewer's own.
export function timeZoneNote(timeZone: string): string {
  return timeZone === NEW_YORK ? 'Times are New York time.' : `Times are your time (${timeZone}).`;
}

// The kinds of tick marks lightweight-charts asks a label for (its TickMarkType enum).
export const Tick = { Year: 0, Month: 1, Day: 2, Time: 3, TimeWithSeconds: 4 } as const;

// Labels on the time axis: a year, a month, a day or a time of day in the user's time format, in
// the style's zone. The day stays short (3 Jun) in every date format, to fit between the ticks.
export function tickFormatter(style: DateStyle) {
  return (seconds: number, tick: number): string => {
    const date = new Date(seconds * 1000);
    if (tick === Tick.Time || tick === Tick.TimeWithSeconds) return formatTime(date, style);
    if (tick === Tick.Day) return formatShortDay(date, style);
    const { year, month } = calendarDay(date, style.timeZone);
    return tick === Tick.Year ? year : monthName(month);
  };
}

// The label under the crosshair: the date and the time as the user writes them, in the style's
// zone.
export function crosshairFormatter(style: DateStyle) {
  return (seconds: number): string => {
    const date = new Date(seconds * 1000);
    return `${formatDate(date, style)}, ${formatTime(date, style)}`;
  };
}

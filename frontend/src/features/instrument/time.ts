import type { Market } from '@/api';

// Stocks trade on New York time (the session opens at 09:30 there); crypto has no home
// exchange clock, so it shows UTC like the API. The chart gets epoch seconds and would show UTC.
export function chartTimeZone(market: Market): string {
  return market === 'stock' ? 'America/New_York' : 'UTC';
}

// The kinds of tick marks lightweight-charts asks a label for (its TickMarkType enum).
export const Tick = { Year: 0, Month: 1, Day: 2, Time: 3, TimeWithSeconds: 4 } as const;

const LOCALE = 'en-GB';

function formatter(timeZone: string, options: Intl.DateTimeFormatOptions) {
  const format = new Intl.DateTimeFormat(LOCALE, { timeZone, ...options });
  return (seconds: number) => format.format(new Date(seconds * 1000));
}

// Labels on the time axis: a year, a month, a day or a time of day, in the market's zone.
export function tickFormatter(timeZone: string) {
  const year = formatter(timeZone, { year: 'numeric' });
  const month = formatter(timeZone, { month: 'short' });
  const day = formatter(timeZone, { day: 'numeric', month: 'short' });
  const time = formatter(timeZone, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
  return (seconds: number, tick: number): string => {
    if (tick === Tick.Year) return year(seconds);
    if (tick === Tick.Month) return month(seconds);
    if (tick === Tick.Day) return day(seconds);
    return time(seconds);
  };
}

// The label under the crosshair: full date and time, in the market's zone.
export function crosshairFormatter(timeZone: string) {
  return formatter(timeZone, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  });
}

// "Data since 27 Jul 2020" on the instrument header.
export function formatDate(seconds: number, timeZone: string): string {
  return formatter(timeZone, { year: 'numeric', month: 'short', day: 'numeric' })(seconds);
}

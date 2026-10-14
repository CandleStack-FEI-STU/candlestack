import type { Instrument } from '@/api';
import { formatPrice, formatSignedChange } from '@/lib/numbers';

// The last daily candles of a list row (#189), as the API sends them: oldest first, one entry per
// day of the market, [open time, open, high, low, close], null for a day without a candle.
export type Spark = Instrument['spark'];
type Day = NonNullable<NonNullable<Spark>[number]>;

// The SVG of the candles: one path per colour (up when the close is at or above the open), and
// the days in their slots (null for a gap) for the hover.
export type CandlePaths = { up: string; down: string; days: (Day | null)[] };

// The last `count` days in `width` × `height` px, a slot each, scaled to their low and high with
// 1 px padding; null without any candle (the placeholder line). Bodies are about 62 % of a slot,
// odd so the 1 px wick sits in their middle, at least 3 px wide and 1 px high (5 px in the 11.2 px
// slots of 10 days in 112 px, 3 px in 44 px for 7).
export function candlePaths(spark: Spark, count: number, width: number, height: number): CandlePaths | null {
  // Fewer days than slots are padded at the start: the newest day is always at the right edge.
  const days: (Day | null)[] = (spark ?? []).slice(-count);
  while (days.length < count) days.unshift(null);
  const candles = days.filter((day) => day !== null);
  if (candles.length === 0) return null;
  const low = Math.min(...candles.map((day) => day[3]));
  const high = Math.max(...candles.map((day) => day[2]));
  const y = (price: number) => (high === low ? height / 2 : 1 + ((high - price) / (high - low)) * (height - 2));
  const slot = width / count;
  let body = Math.floor(slot * 0.62);
  if (body % 2 === 0) body -= 1;
  body = Math.max(3, body);
  const paths = { up: '', down: '' };
  days.forEach((day, index) => {
    if (day === null) return;
    const [, open, dayHigh, dayLow, close] = day;
    const x = Math.round(index * slot + (slot - body) / 2);
    const wick = x + (body - 1) / 2;
    const top = Math.round(y(dayHigh));
    const bottom = Math.max(top + 1, Math.round(y(dayLow)));
    const bodyTop = Math.round(y(Math.max(open, close)));
    const bodyBottom = Math.max(bodyTop + 1, Math.round(y(Math.min(open, close))));
    paths[close >= open ? 'up' : 'down'] +=
      `M${wick} ${top}h1V${bottom}h-1ZM${x} ${bodyTop}h${body}V${bodyBottom}h-${body}Z`;
  });
  return { ...paths, days };
}

// What a screen reader hears: "10 daily candles, +2.15%", the candles there are (not the empty
// days) and the change from the first open to the last close.
export function candlesLabel(days: readonly (Day | null)[]): string {
  const candles = days.filter((day) => day !== null);
  const first = candles[0];
  const last = candles.at(-1);
  if (!first || !last) return 'No chart yet';
  const change = formatSignedChange((last[4] / first[1] - 1) * 100);
  return `${candles.length} daily ${candles.length === 1 ? 'candle' : 'candles'}, ${change}`;
}

// UTC: a crypto day starts at 00:00 UTC, a stock's session opens at 13:30 or 14:30 UTC.
const DATE = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });

// The hover text of a day: "Oct 9 · close 82,635.55".
export function dayLabel(day: Day): string {
  return `${DATE.format(day[0] * 1000)} · close ${formatPrice(day[4])}`;
}

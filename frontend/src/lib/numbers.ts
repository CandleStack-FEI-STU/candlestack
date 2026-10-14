// How the app writes market numbers, the same in the instrument list (#184) and the chart legend
// (#113): prices, changes and volumes. Numbers are shown in Geist Mono, so the digits line up; a
// missing number is a dash.

export const NO_VALUE = '—';

const fixed = new Map<number, Intl.NumberFormat>();
const SIGNIFICANT = new Intl.NumberFormat('en-US', { maximumSignificantDigits: 4 });
const COMPACT = new Intl.NumberFormat('en-US', { notation: 'compact', maximumSignificantDigits: 3 });

// Decimals for a price: 2 from 10 (83,249.35), 4 between 1 and 10 (1.3662), 4 significant digits
// below 1, so a cheap coin does not read 0.00 (0.08438, 0.0000042; at most 10).
export function priceDecimals(price: number): number {
  const abs = Math.abs(price);
  if (!Number.isFinite(abs) || abs === 0 || abs >= 10) return 2;
  if (abs >= 1) return 4;
  return Math.min(10, 3 - Math.floor(Math.log10(abs)));
}

// A price with exactly `decimals` decimals and thousands separators: the chart legend writes
// every price of a chart with the decimals of its latest close, so they line up.
export function formatPriceWith(price: number, decimals: number): string {
  let format = fixed.get(decimals);
  if (!format) {
    format = new Intl.NumberFormat('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
    fixed.set(decimals, format);
  }
  return format.format(price);
}

// A price on its own, with its own decimals (priceDecimals); below 1 without trailing zeros.
export function formatPrice(price: number | null): string {
  if (price === null) return NO_VALUE;
  return Math.abs(price) >= 1 ? formatPriceWith(price, priceDecimals(price)) : SIGNIFICANT.format(price);
}

// 3 significant digits: 1.26B, 685M, 4.1M, 62K, 7.67.
export function formatCompact(value: number): string {
  return COMPACT.format(value);
}

// USD with 3 significant digits: $1.26B, $685M, $4.1M, $62K.
export function formatVolume(volume: number | null): string {
  return volume === null ? NO_VALUE : `$${formatCompact(volume)}`;
}

// Up, down, or flat when it rounds to 0.00 % (no triangle, muted); none without a change.
export type ChangeTone = 'up' | 'down' | 'flat' | 'none';

export function changeTone(change: number | null): ChangeTone {
  if (change === null) return 'none';
  const hundredths = Math.round(change * 100);
  if (hundredths > 0) return 'up';
  return hundredths < 0 ? 'down' : 'flat';
}

// Without a sign, next to the triangle that shows the direction: 1.51%.
export function formatChange(change: number | null): string {
  return change === null ? NO_VALUE : `${formatPriceWith(Math.abs(change), 2)}%`;
}

// With its sign, where there is no triangle: +1.51%, −0.71% (a minus sign), 0.00%.
export function formatSignedChange(change: number | null): string {
  if (change === null) return NO_VALUE;
  const sign = { up: '+', down: '−', flat: '', none: '' }[changeTone(change)];
  return `${sign}${formatChange(change)}`;
}

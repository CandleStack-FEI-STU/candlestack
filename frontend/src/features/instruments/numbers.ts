// How the instrument list writes its 24 h stats (#184). Every number is in Geist Mono, so the
// digits line up; a missing number is a dash.

export const NO_VALUE = '—';

const TWO = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const FOUR = new Intl.NumberFormat('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 4 });
const SIGNIFICANT = new Intl.NumberFormat('en-US', { maximumSignificantDigits: 4 });
const COMPACT = new Intl.NumberFormat('en-US', { notation: 'compact', maximumSignificantDigits: 3 });

// 2 decimals from 10 (83,249.35), 4 between 1 and 10 (1.3662), up to 4 significant digits below 1
// (0.08438, 0.0000042).
export function formatPrice(price: number | null): string {
  if (price === null) return NO_VALUE;
  if (price >= 10) return TWO.format(price);
  if (price >= 1) return FOUR.format(price);
  return SIGNIFICANT.format(price);
}

// USD with 3 significant digits: $1.26B, $685M, $4.1M, $62K.
export function formatVolume(volume: number | null): string {
  return volume === null ? NO_VALUE : `$${COMPACT.format(volume)}`;
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
  return change === null ? NO_VALUE : `${TWO.format(Math.abs(change))}%`;
}

// With its sign, where there is no room for the triangle (phones): +1.51%, −0.71%, 0.00%.
export function formatSignedChange(change: number | null): string {
  if (change === null) return NO_VALUE;
  const sign = { up: '+', down: '−', flat: '', none: '' }[changeTone(change)];
  return `${sign}${formatChange(change)}`;
}

import { formatPriceWith } from './numbers';

// How the app writes a backtest's results (mockups/app: pct, num, fmtN), the same on the
// Backtests page, the dashboard and the Models page. The API sends returns and rates as fractions
// (0.246 is 24.6 %). Signs are real minus signs and come from the rounded value, so −0.004 reads
// as 0.00, not −0.00. A missing value (a failed backtest) is an en dash.

export const MISSING = '–';

// With its sign, as text: the digits and whether the rounded value is below zero.
function signed(value: number, decimals: number): { text: string; negative: boolean } {
  const text = formatPriceWith(Math.abs(value), decimals);
  return { text, negative: value < 0 && /[1-9]/.test(text) };
}

// A Sharpe ratio with 2 decimals: 1.34, −0.18.
export function formatSharpe(sharpe: number | null): string {
  if (sharpe === null) return MISSING;
  const { text, negative } = signed(sharpe, 2);
  return negative ? `−${text}` : text;
}

// A return or a drawdown with one decimal and always a sign, a space before the percent sign:
// +96.5 %, −24.1 %.
export function formatPercent(fraction: number | null): string {
  if (fraction === null) return MISSING;
  const { text, negative } = signed(fraction * 100, 1);
  return `${negative ? '−' : '+'}${text} %`;
}

// The colour of a return: up from zero, down below it (as it is written, rounded).
export function returnTone(fraction: number): 'up' | 'down' {
  return signed(fraction * 100, 1).negative ? 'down' : 'up';
}

// A share of the trades without a sign: 55.6 %.
export function formatWinRate(fraction: number | null): string {
  return fraction === null ? MISSING : `${formatPriceWith(fraction * 100, 1)} %`;
}

// A count with thousands separators: 1,712.
export function formatCount(count: number | null): string {
  return count === null ? MISSING : formatPriceWith(count, 0);
}

import { calendarDay, formatDate, formatShortDay, type DateStyle } from '@/lib/dates';

// How the Models part writes sizes, parameters, shapes and dates (mockups/app, the Models page
// and the upload dialog). Megabytes are binary, as the API's limits: 1 MB = 1,048,576 bytes.

const MB = 1024 * 1024;
const ONE_DECIMAL = new Intl.NumberFormat('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const UP_TO_ONE_DECIMAL = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 });
const GROUPED = new Intl.NumberFormat('en-US');

// A file that is not empty never reads 0.0 MB: it takes some of the storage.
const megabytes = (bytes: number) => (bytes > 0 ? Math.max(bytes / MB, 0.1) : 0);

// A file's size with one decimal: 14.2 MB, 3.0 MB.
export function formatSize(bytes: number): string {
  return `${ONE_DECIMAL.format(megabytes(bytes))} MB`;
}

// Storage in MB without a trailing zero, as the mockup writes it: 0, 29.5, 100.
export function formatMegabytes(bytes: number): string {
  return UP_TO_ONE_DECIMAL.format(megabytes(bytes));
}

// `{used} MB of {quota} MB`, the storage the user's models take.
export function formatUsage(used: number, quota: number): string {
  return `${formatMegabytes(used)} MB of ${formatMegabytes(quota)} MB`;
}

// From 100,000 in millions with 2 decimals (1.24 M), below it the grouped digits (9,325).
export function formatParameters(count: number): string {
  if (count >= 100_000) return `${(count / 1_000_000).toFixed(2)} M`;
  return GROUPED.format(count);
}

// The shape a model reads and gives: "25×23 → 1" on a tile, "25 × 23 → 1" spaced in the upload
// dialog. Without an input shape there is nothing to say (null); without an output, the input.
export function formatShape(input: number[] | null, output: number[] | null, spaced = false): string | null {
  if (input === null || input.length === 0) return null;
  const times = spaced ? ' × ' : '×';
  const text = input.join(times);
  return output === null || output.length === 0 ? text : `${text} → ${output.join(times)}`;
}

// A Sharpe ratio with 2 decimals and a real minus sign; an en dash without one.
export function formatSharpe(sharpe: number | null): string {
  if (sharpe === null) return '–';
  return `${sharpe < 0 ? '−' : ''}${Math.abs(sharpe).toFixed(2)}`;
}

// When a model was added, the day in the user's zone: "Today", or the day in the user's date
// format (13 Oct 2025, 2025-10-13, 13.10.2025). The mockup's "13 Oct" keeps its year out in the
// default format while it is this year's; the numeric formats always write the whole date.
export function formatAdded(iso: string, style: Pick<DateStyle, 'timeZone' | 'dateFormat'>, now = new Date()): string {
  const date = new Date(iso);
  const day = calendarDay(date, style.timeZone);
  const today = calendarDay(now, style.timeZone);
  if (day.year === today.year && day.month === today.month && day.day === today.day) return 'Today';
  if (style.dateFormat === 'dmy' && day.year === today.year) return formatShortDay(date, style);
  return formatDate(date, style);
}

// "lstm.keras" as its stem "lstm" and the extension ".keras", which a rename keeps.
export function splitExtension(name: string): [string, string] {
  const dot = name.lastIndexOf('.');
  return dot > 0 ? [name.slice(0, dot), name.slice(dot)] : [name, ''];
}

// A count with its noun: 1 model, 3 models; 1 backtest, 0 backtests.
export function plural(count: number, noun: string): string {
  return `${count} ${count === 1 ? noun : `${noun}s`}`;
}

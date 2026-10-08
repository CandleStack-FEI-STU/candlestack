import type { components } from './schema';

export type Timeframe = components['schemas']['Timeframe'];

export const TIMEFRAMES: readonly Timeframe[] = ['1m', '5m', '15m', '1h', '4h', '1d'];
export const DEFAULT_TIMEFRAME: Timeframe = '1h';

// For search params: anything that is not a known timeframe becomes the default.
export function parseTimeframe(value: unknown): Timeframe {
  return TIMEFRAMES.includes(value as Timeframe) ? (value as Timeframe) : DEFAULT_TIMEFRAME;
}

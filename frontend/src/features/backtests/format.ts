import type { Backtest, Representation } from '@/api';
import { returnTone } from '@/lib/results';

// How the backtests' own parts are written (mockups/app: REP, instList, ichips); their results go
// through src/lib/results.ts.

const REPRESENTATIONS: Record<Representation, string> = { renko: 'Renko', kagi: 'Kagi', windows: 'Time windows' };

export function representationName(representation: Representation): string {
  return REPRESENTATIONS[representation];
}

// Whether a backtest has results to show: a finished one. A failed one shows the Failed badge and
// dashes, with no line and no Sharpe ratio.
export const hasResults = (backtest: Backtest) => backtest.status === 'finished';

// The colour of a return, the only result with one: green from zero, red below.
export const returnClass = (fraction: number) => (returnTone(fraction) === 'up' ? 'text-up' : 'text-down');

export const symbolsOf = (backtest: Backtest) => backtest.instruments.map((instrument) => instrument.symbol);

// The instruments in a sentence: "AAPL", "MSFT and GOOGL", "AAPL, MSFT, NVDA, SPY and TSLA", and
// from six on the first three and how many more: "AAPL, MSFT, NVDA and 5 more".
export function instrumentList(symbols: readonly string[]): string {
  if (symbols.length <= 1) return symbols.join('');
  if (symbols.length <= 5) return `${symbols.slice(0, -1).join(', ')} and ${symbols.at(-1)}`;
  return `${symbols.slice(0, 3).join(', ')} and ${symbols.length - 3} more`;
}

// The chips a row has room for: up to `max` symbols, or `max - 1` and a "+N" chip for the rest.
export function chipsOf(symbols: readonly string[], max: number): string[] {
  if (symbols.length <= max) return [...symbols];
  return [...symbols.slice(0, max - 1), `+${symbols.length - max + 1}`];
}

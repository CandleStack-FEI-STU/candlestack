// A noun for a count: backtest for 1, backtests otherwise (0 backtests).
export function pluralNoun(count: number, noun: string): string {
  return count === 1 ? noun : `${noun}s`;
}

// A count with its noun: 1 model, 3 models.
export function plural(count: number, noun: string): string {
  return `${count} ${pluralNoun(count, noun)}`;
}

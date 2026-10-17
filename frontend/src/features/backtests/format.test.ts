import { describe, expect, it } from 'vitest';

import { backtest, failedBacktest } from '@/test/api';

import { chipsOf, hasResults, instrumentList, representationName } from './format';

describe('hasResults', () => {
  it('is true for a finished backtest only', () => {
    expect(hasResults(backtest())).toBe(true);
    expect(hasResults(failedBacktest())).toBe(false);
    expect(hasResults(backtest({ status: 'running' }))).toBe(false);
  });
});

describe('instrumentList', () => {
  it('writes one, a few, or the first three and how many more', () => {
    expect(instrumentList(['AAPL'])).toBe('AAPL');
    expect(instrumentList(['MSFT', 'GOOGL'])).toBe('MSFT and GOOGL');
    expect(instrumentList(['AAPL', 'MSFT', 'NVDA', 'SPY', 'TSLA'])).toBe('AAPL, MSFT, NVDA, SPY and TSLA');
    expect(instrumentList(['AAPL', 'MSFT', 'NVDA', 'SPY', 'TSLA', 'AMD', 'META', 'QQQ'])).toBe(
      'AAPL, MSFT, NVDA and 5 more',
    );
  });
});

describe('chipsOf', () => {
  it('shows every symbol that fits, else one less and the rest as +N', () => {
    expect(chipsOf(['AAPL', 'MSFT'], 2)).toEqual(['AAPL', 'MSFT']);
    expect(chipsOf(['AAPL', 'MSFT', 'NVDA'], 2)).toEqual(['AAPL', '+2']);
    expect(chipsOf(['AAPL', 'MSFT', 'NVDA'], 3)).toEqual(['AAPL', 'MSFT', 'NVDA']);
    expect(chipsOf(['AAPL', 'MSFT', 'NVDA', 'SPY', 'TSLA'], 3)).toEqual(['AAPL', 'MSFT', '+3']);
  });
});

describe('representationName', () => {
  it('names the three representations', () => {
    expect(['renko', 'kagi', 'windows'].map((each) => representationName(each as 'renko'))).toEqual([
      'Renko',
      'Kagi',
      'Time windows',
    ]);
  });
});

import { describe, expect, it } from 'vitest';

import { EXCHANGES, exchangeLabel, exchangeMarket, onlyExchange } from './exchanges';

describe('exchanges', () => {
  it('lists the stock exchanges, then Binance, which has the crypto pairs', () => {
    expect(EXCHANGES).toEqual(['NASDAQ', 'NYSE', 'ARCA', 'AMEX', 'BATS', 'BINANCE']);
    expect(EXCHANGES.map(exchangeMarket)).toEqual(['stock', 'stock', 'stock', 'stock', 'stock', 'crypto']);
  });

  it('names Binance as the company writes it, a stock exchange by its code, and an unknown one as it is', () => {
    expect(EXCHANGES.map(exchangeLabel)).toEqual(['NASDAQ', 'NYSE', 'ARCA', 'AMEX', 'BATS', 'Binance']);
    expect(exchangeLabel('IEX')).toBe('IEX');
    expect(exchangeLabel('toString')).toBe('toString');
  });

  it('knows the exchange of a market that has only one', () => {
    expect(onlyExchange('crypto')).toBe('BINANCE');
    expect(onlyExchange('stock')).toBeUndefined();
  });
});

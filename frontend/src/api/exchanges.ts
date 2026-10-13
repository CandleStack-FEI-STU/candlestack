import type { components } from './schema';

export type Exchange = components['schemas']['Exchange'];
type Market = components['schemas']['Market'];

// Every exchange the API filters by, in the order the filter shows them (the stock exchanges,
// then Binance, where the crypto pairs trade): its market and how the app names it, Binance as the
// company writes it and the stock exchanges by their code. Keyed by the generated type, so a value
// the API adds or drops fails the type check.
const TABLE: Record<Exchange, { market: Market; label: string }> = {
  NASDAQ: { market: 'stock', label: 'NASDAQ' },
  NYSE: { market: 'stock', label: 'NYSE' },
  ARCA: { market: 'stock', label: 'ARCA' },
  AMEX: { market: 'stock', label: 'AMEX' },
  BATS: { market: 'stock', label: 'BATS' },
  BINANCE: { market: 'crypto', label: 'Binance' },
};

export const EXCHANGES = Object.keys(TABLE) as Exchange[];

const isExchange = (value: string): value is Exchange => Object.hasOwn(TABLE, value);

// The market whose instruments trade on an exchange.
export function exchangeMarket(exchange: Exchange): Market {
  return TABLE[exchange].market;
}

// An exchange as the app names it; a code the table does not know as it is.
export function exchangeLabel(exchange: string): string {
  return isExchange(exchange) ? TABLE[exchange].label : exchange;
}

// The exchange of a market whose instruments all trade on one (crypto: Binance), if there is one.
export function onlyExchange(market: Market): Exchange | undefined {
  const found = EXCHANGES.filter((exchange) => TABLE[exchange].market === market);
  return found.length === 1 ? found[0] : undefined;
}

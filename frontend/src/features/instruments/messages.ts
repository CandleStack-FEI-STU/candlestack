import { ApiError, type Market } from '@/api';

const MARKET_NAMES: Record<Market, string> = { stock: 'Stocks', crypto: 'Crypto pairs' };

// What to say when nothing matches: name the query and the market, so the user sees why.
export function emptyMessage(query: string, market: Market | undefined): string {
  const where = market === undefined ? '' : ` in ${MARKET_NAMES[market].toLowerCase()}`;
  if (query === '') return `No instruments${where}.`;
  return `No instruments match “${query}”${where}. Try a symbol like btc or a name like apple.`;
}

// A market whose list could not be loaded is left out of the search: say which one.
export function unavailableMessage(markets: readonly Market[]): string | undefined {
  if (markets.length === 0) return undefined;
  const names = markets.map((market) => MARKET_NAMES[market]).join(' and ');
  return `${names} cannot be searched right now; the results show the rest. Try again in a minute.`;
}

// API errors in plain words. The API's own `detail` already says what went wrong.
export function errorMessage(error: Error): string {
  if (!(error instanceof ApiError)) return 'Something went wrong. Reload the page.';
  if (error.status === 0) return error.message;
  const wait = error.retryAfter === undefined ? '' : ` Try again in ${error.retryAfter} s.`;
  return `The instrument list could not be loaded: ${error.message}${wait}`;
}

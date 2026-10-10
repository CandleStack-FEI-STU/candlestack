import { ApiError, type Exchange, type Market } from '@/api';

const MARKET_NAMES: Record<Market, string> = { stock: 'Stocks', crypto: 'Crypto pairs' };

// What to say when nothing matches: name the query, the market and the exchange, so the user
// sees why.
export function emptyMessage(query: string, market: Market | undefined, exchange?: Exchange): string {
  const inMarket = market === undefined ? '' : ` in ${MARKET_NAMES[market].toLowerCase()}`;
  const where = exchange === undefined ? inMarket : `${inMarket} on ${exchange}`;
  if (query === '') return `No instruments${where}.`;
  return `No instruments match “${query}”${where}. Try a symbol like btc or a name like apple.`;
}

// A market whose list could not be loaded is left out of the search: say which one.
export function unavailableMessage(markets: readonly Market[]): string | undefined {
  if (markets.length === 0) return undefined;
  const names = markets.map((market) => MARKET_NAMES[market]).join(' and ');
  return `${names} cannot be searched right now; the results show the rest. Try again in a minute.`;
}

// An error of the list in plain words: what happened, what to do, whether "Try again" can help,
// and the server's own words in small print for whoever reports it.
export type ListError = { title: string; hint: string; canRetry: boolean; tone: 'warn' | 'error'; detail?: string };

type Text = Omit<ListError, 'detail'>;

function waitHint(seconds: number | undefined): string {
  return seconds === undefined ? 'Try again in a minute.' : `Try again in ${seconds} s.`;
}

// The API before #105 (still on prod until the next release) cannot list without a query and
// answers 422. Retrying does not help; typing a query does.
const OLD_API: Text = {
  title: 'This server cannot show the whole list yet.',
  hint: 'It runs an older version of the API that only searches. Type a symbol or a name above, for example btc or apple.',
  canRetry: false,
  tone: 'warn',
};

function serverText(error: ApiError): Text {
  if (error.status === 503) {
    return {
      title: 'The instrument catalog is unavailable right now.',
      hint: `The data source did not answer. ${waitHint(error.retryAfter)}`,
      canRetry: true,
      tone: 'error',
    };
  }
  return {
    title: 'The server ran into a problem.',
    hint: 'This is not caused by your search. Try again in a minute; if it keeps happening, tell the team.',
    canRetry: true,
    tone: 'error',
  };
}

function apiText(error: ApiError, query: string): Text {
  if (error.status === 0) {
    return {
      title: 'No connection to the CandleStack server.',
      hint: 'Check your internet connection, then try again.',
      canRetry: true,
      tone: 'error',
    };
  }
  if (error.status === 422 && query === '') return OLD_API;
  if (error.status === 422) {
    return {
      title: 'The server did not accept this search.',
      hint: 'Try a shorter query: a symbol like btc or a name like apple.',
      canRetry: false,
      tone: 'warn',
    };
  }
  if (error.status === 429) {
    return { title: 'Too many requests.', hint: waitHint(error.retryAfter), canRetry: true, tone: 'warn' };
  }
  if (error.status >= 500) return serverText(error);
  return {
    title: 'The instrument list could not be loaded.',
    hint: 'Reload the page; if it keeps happening, tell the team.',
    canRetry: true,
    tone: 'error',
  };
}

// The list's error for the query it was loading.
export function describeListError(error: Error, query: string): ListError {
  if (!(error instanceof ApiError)) {
    return {
      title: 'Something went wrong in the app.',
      hint: 'Reload the page; if it keeps happening, tell the team.',
      canRetry: true,
      tone: 'error',
      detail: error.message,
    };
  }
  const detail = error.status === 0 ? undefined : `Server: ${error.message} (HTTP ${error.status})`;
  return { ...apiText(error, query), detail };
}

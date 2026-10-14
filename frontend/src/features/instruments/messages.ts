import { ApiError, exchangeLabel, exchangeMarket, type Exchange, type Market } from '@/api';

// How the list names a market: `type` where it is picked (the Filters button and panel, "Crypto
// only"), like the timeframe or a tab; `items` in sentences about what is listed ("No crypto
// pairs on NYSE"), where "crypto" alone would not say what is missing.
export const MARKET_NAMES: Record<Market, { type: string; items: string }> = {
  stock: { type: 'Stocks', items: 'stocks' },
  crypto: { type: 'Crypto', items: 'crypto pairs' },
};

const capitalised = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

// What to say when nothing matches: name the query, the market and the exchange, so the user
// sees why.
export function emptyMessage(query: string, market: Market | undefined, exchange?: Exchange): string {
  const inMarket = market === undefined ? '' : ` in ${MARKET_NAMES[market].items}`;
  const where = exchange === undefined ? inMarket : `${inMarket} on ${exchangeLabel(exchange)}`;
  if (query === '') return `No instruments${where}.`;
  return `No instruments match “${query}”${where}. Try a symbol like btc or a name like apple.`;
}

// What to say for a link that pairs a market with an exchange it does not trade on
// (?market=crypto&exchange=NYSE): the controls cannot make one, an old or hand-edited link can.
export function mismatchMessage(market: Market, exchange: Exchange): { title: string; hint: string } {
  const name = exchangeLabel(exchange);
  const lists = MARKET_NAMES[exchangeMarket(exchange)].items;
  return { title: `No ${MARKET_NAMES[market].items} on ${name}`, hint: `${name} lists ${lists} only.` };
}

// A market whose list could not be loaded is left out of the search: say which one.
export function unavailableMessage(markets: readonly Market[]): string | undefined {
  if (markets.length === 0) return undefined;
  const names = capitalised(markets.map((market) => MARKET_NAMES[market].items).join(' and '));
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
// answers 422 about `q`. Retrying does not help; typing a query does.
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

// A 422 names the parameter it rejected, e.g. "query parameter 'q': ...". The hint follows it:
// with an empty query, a complaint about `q` is the old API; with a query, it is the query.
function rejectedText(error: ApiError, query: string): Text {
  const about = (name: string) => error.message.includes(`'${name}'`);
  if (about('q') && query === '') return OLD_API;
  const title = 'The server did not accept this search.';
  const warn = { canRetry: false, tone: 'warn' } as const;
  if (about('q')) return { title, hint: 'Try a shorter query: a symbol like btc or a name like apple.', ...warn };
  return { title, hint: 'Start again from the plain list, without filters or a page in the address.', ...warn };
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
  if (error.status === 422) return rejectedText(error, query);
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

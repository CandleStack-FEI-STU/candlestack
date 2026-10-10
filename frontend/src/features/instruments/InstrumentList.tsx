import { useQuery } from '@tanstack/react-query';

import { hasNextPage, instrumentSearchQueryOptions, type Market } from '@/api';
import { Button } from '@/components/ui/button';

import { InstrumentTable } from './InstrumentTable';
import { describeListError, emptyMessage, unavailableMessage, type ListError } from './messages';
import { Pager } from './Pager';

// Rows per page. The API allows up to 100; 50 fits a screen or two.
export const LIST_PAGE_SIZE = 50;

type Props = { query: string; market: Market | undefined; page: number };

function Note({ children, tone = 'muted' }: { children: string; tone?: 'muted' | 'error' }) {
  const color = tone === 'error' ? 'text-destructive' : 'text-muted-foreground';
  return <p className={`px-3 py-12 text-center text-sm ${color}`}>{children}</p>;
}

// What went wrong, what to do about it, and the server's words in small print.
function ErrorState({ error, onRetry }: { error: ListError; onRetry: () => void }) {
  return (
    <div role="alert" className="mx-auto flex max-w-md flex-col items-center gap-2 py-12 text-center text-sm">
      <p className={error.tone === 'warn' ? 'font-medium text-warn' : 'font-medium text-destructive'}>{error.title}</p>
      <p className="text-muted-foreground">{error.hint}</p>
      {error.canRetry && (
        <Button variant="outline" size="sm" className="mt-2" onClick={onRetry}>
          Try again
        </Button>
      )}
      {error.detail && <p className="mt-3 font-mono text-xs text-muted-foreground/70">{error.detail}</p>}
    </div>
  );
}

// The search result for the query, market and page in the URL, with its empty and error states.
export function InstrumentList({ query, market, page }: Props) {
  const params = { q: query, market, limit: LIST_PAGE_SIZE, offset: (page - 1) * LIST_PAGE_SIZE };
  const result = useQuery(instrumentSearchQueryOptions(params));

  if (result.isPending) return <Note>Loading instruments…</Note>;
  if (result.isError) {
    return <ErrorState error={describeListError(result.error, query)} onRetry={() => void result.refetch()} />;
  }

  const { data } = result;
  const unavailable = unavailableMessage(data.unavailable);
  return (
    <>
      {unavailable && <p className="mb-3 rounded-md border px-3 py-2 text-sm text-warn">{unavailable}</p>}
      <div className={result.isPlaceholderData ? 'rounded-lg border opacity-60' : 'rounded-lg border'}>
        {data.items.length === 0 ? <Note>{emptyMessage(query, market)}</Note> : <InstrumentTable items={data.items} />}
      </div>
      <Pager
        page={page}
        hasNext={hasNextPage(data, LIST_PAGE_SIZE)}
        total={(data as { total?: number }).total}
        pageSize={LIST_PAGE_SIZE}
      />
    </>
  );
}

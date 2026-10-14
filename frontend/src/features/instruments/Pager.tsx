import { Link } from '@tanstack/react-router';

import { cn } from '@/lib/utils';

import { lastPage } from './pagination';

type Props = { page: number; hasNext: boolean; total: number | undefined; pageSize: number; loading: boolean };

const LINK = 'rounded-md border px-3 py-1.5 text-sm transition-colors hover:bg-accent';
const DISABLED = 'opacity-40';

// A link to another page, or a plain label when there is none: a disabled link would still be
// a link for the keyboard, screen readers and a middle click.
function PageLink({ page, enabled, children }: { page: number | undefined; enabled: boolean; children: string }) {
  if (!enabled) {
    return (
      <span aria-disabled="true" className={cn(LINK, DISABLED)}>
        {children}
      </span>
    );
  }
  return (
    <Link from="/instruments" search={(prev) => ({ ...prev, page })} className={LINK}>
      {children}
    </Link>
  );
}

// "Page 2 of 31" with previous and next. The page is in the URL, so Back steps through pages.
// While a page loads, the previous one stays on screen with its own `hasNext` and `total`, so
// both links wait: two quick clicks on Next would otherwise skip a page or run past the end.
export function Pager({ page, hasNext, total, pageSize, loading }: Props) {
  if (page === 1 && !hasNext) return null;
  const pages = total === undefined ? undefined : lastPage(total, pageSize);

  return (
    <nav aria-label="Pages" className="mt-4 flex items-center justify-between gap-3">
      <PageLink page={page > 2 ? page - 1 : undefined} enabled={page > 1 && !loading}>
        Previous
      </PageLink>
      <span className="text-sm text-muted-foreground">
        Page {page}
        {pages === undefined ? '' : ` of ${pages}`}
      </span>
      <PageLink page={page + 1} enabled={hasNext && !loading}>
        Next
      </PageLink>
    </nav>
  );
}

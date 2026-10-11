import { Link } from '@tanstack/react-router';

import { cn } from '@/lib/utils';

type Props = { page: number; hasNext: boolean; total: number | undefined; pageSize: number };

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
    <Link from="/" search={(prev) => ({ ...prev, page })} className={LINK}>
      {children}
    </Link>
  );
}

// "Page 2 of 31" with previous and next. The page is in the URL, so Back steps through pages.
export function Pager({ page, hasNext, total, pageSize }: Props) {
  if (page === 1 && !hasNext) return null;
  const pages = total === undefined ? undefined : Math.max(1, Math.ceil(total / pageSize));

  return (
    <nav aria-label="Pages" className="mt-4 flex items-center justify-between gap-3">
      <PageLink page={page > 2 ? page - 1 : undefined} enabled={page > 1}>
        Previous
      </PageLink>
      <span className="text-sm text-muted-foreground">
        Page {page}
        {pages === undefined ? '' : ` of ${pages}`}
      </span>
      <PageLink page={page + 1} enabled={hasNext}>
        Next
      </PageLink>
    </nav>
  );
}

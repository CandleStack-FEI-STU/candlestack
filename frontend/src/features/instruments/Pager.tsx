import { Link } from '@tanstack/react-router';

import { cn } from '@/lib/utils';

type Props = { page: number; hasNext: boolean; total: number | undefined; pageSize: number };

const LINK = 'rounded-md border px-3 py-1.5 text-sm transition-colors hover:bg-accent';
const DISABLED = 'pointer-events-none opacity-40';

// "Page 2 of 31" with previous and next. The page is in the URL, so Back steps through pages.
export function Pager({ page, hasNext, total, pageSize }: Props) {
  if (page === 1 && !hasNext) return null;
  const pages = total === undefined ? undefined : Math.max(1, Math.ceil(total / pageSize));

  return (
    <nav aria-label="Pages" className="mt-4 flex items-center justify-between gap-3">
      <Link
        from="/"
        search={(prev) => ({ ...prev, page: page > 2 ? page - 1 : undefined })}
        aria-disabled={page === 1}
        tabIndex={page === 1 ? -1 : undefined}
        className={cn(LINK, page === 1 && DISABLED)}
      >
        Previous
      </Link>
      <span className="text-sm text-muted-foreground">
        Page {page}
        {pages === undefined ? '' : ` of ${pages}`}
      </span>
      <Link
        from="/"
        search={(prev) => ({ ...prev, page: page + 1 })}
        aria-disabled={!hasNext}
        tabIndex={hasNext ? undefined : -1}
        className={cn(LINK, !hasNext && DISABLED)}
      >
        Next
      </Link>
    </nav>
  );
}

import { Search } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { Input } from '@/components/ui/input';
import { useDebouncedValue } from '@/lib/useDebouncedValue';
import { cn } from '@/lib/utils';

type Props = {
  query: string;
  onSearch: (query: string) => void;
  placeholder: string;
  label: string;
  // The API's limit for the query.
  maxLength: number;
  // How long typing has to pause before the search runs: one request for "btc", not three.
  debounceMs: number;
  className?: string;
};

// A search field with the magnifier inside at the left (36 px high, as mockups/app .bt-q), on
// the instrument list and the backtests. The input keeps its own text while the user types; the
// URL (and so the request) follows once the typing pauses. Back and forward change `query`, and
// the input follows that too.
export function SearchBox({ query, onSearch, placeholder, label, maxLength, debounceMs, className }: Props) {
  const [text, setText] = useState(query);
  const debounced = useDebouncedValue(text, debounceMs);
  const sent = useRef(query);
  const search = useRef(onSearch);

  useEffect(() => {
    search.current = onSearch;
  }, [onSearch]);

  useEffect(() => {
    const next = debounced.trim();
    if (next === sent.current) return;
    sent.current = next;
    search.current(next);
  }, [debounced]);

  useEffect(() => {
    if (query === sent.current) return;
    sent.current = query;
    setText(query);
  }, [query]);

  return (
    <div className={cn('relative w-full sm:max-w-sm', className)}>
      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        type="search"
        value={text}
        onChange={(event) => setText(event.target.value)}
        maxLength={maxLength}
        placeholder={placeholder}
        aria-label={label}
        className="h-9 pr-3 pl-9"
      />
    </div>
  );
}

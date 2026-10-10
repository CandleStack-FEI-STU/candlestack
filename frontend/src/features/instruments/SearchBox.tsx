import { Search } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { useDebouncedValue } from '@/lib/useDebouncedValue';

// How long typing has to pause before the search runs: one request for "btc", not three.
const DEBOUNCE_MS = 300;

type Props = { query: string; onSearch: (query: string) => void };

// The input keeps its own text while the user types; the URL (and so the request) follows once
// the typing pauses. Back and forward change `query`, and the input follows that too.
export function SearchBox({ query, onSearch }: Props) {
  const [text, setText] = useState(query);
  const debounced = useDebouncedValue(text, DEBOUNCE_MS);
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
    <div className="relative w-full sm:max-w-sm">
      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
      <input
        type="search"
        value={text}
        onChange={(event) => setText(event.target.value)}
        maxLength={50}
        placeholder="Symbol or name, e.g. btc or apple"
        aria-label="Search instruments by symbol or name"
        className="h-9 w-full rounded-md border bg-background pr-3 pl-9 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
      />
    </div>
  );
}

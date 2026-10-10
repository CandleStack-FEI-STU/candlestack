import { useQuery } from '@tanstack/react-query';
import { Link, useRouterState } from '@tanstack/react-router';
import { Search } from 'lucide-react';
import { useRef, useState, type FocusEvent, type KeyboardEvent, type RefObject } from 'react';

import { instrumentSearchQueryOptions, type Instrument } from '@/api';
import { useDebouncedValue } from '@/lib/useDebouncedValue';

import { moveActive } from './quickSearchKeys';

// A short list is enough to jump to an instrument; "All results" opens the full list.
const LIMIT = 8;
const DEBOUNCE_MS = 250;
const ITEM = 'flex items-center gap-3 px-3 py-1.5 outline-none hover:bg-accent focus-visible:bg-accent';

// Arrow keys move the focus between the links in the list; Escape goes back to the input.
function onListKey(event: KeyboardEvent<HTMLAnchorElement>, input: RefObject<HTMLInputElement | null>) {
  if (event.key === 'Escape') return input.current?.focus();
  const links = [...(event.currentTarget.closest('ul')?.querySelectorAll('a') ?? [])];
  const at = links.indexOf(event.currentTarget);
  if (event.key === 'ArrowUp' && at === 0) return input.current?.focus();
  const next = moveActive(at, event.key, links.length);
  if (next === at) return;
  event.preventDefault();
  links[next]?.focus();
}

type ResultsProps = {
  q: string;
  items: readonly Instrument[];
  pending: boolean;
  tf: string | undefined;
  input: RefObject<HTMLInputElement | null>;
  onPick: () => void;
};

function Results({ q, items, pending, tf, input, onPick }: ResultsProps) {
  const onKeyDown = (event: KeyboardEvent<HTMLAnchorElement>) => onListKey(event, input);
  return (
    <ul className="absolute top-full right-0 z-20 mt-1 w-full max-w-[calc(100vw-2rem)] min-w-72 overflow-hidden rounded-md border bg-background py-1 text-sm shadow-lg">
      {pending && <li className="px-3 py-1.5 text-muted-foreground">Searching…</li>}
      {items.map((item) => (
        <li key={item.id}>
          <Link
            to="/instrument/$id"
            params={{ id: item.id }}
            search={{ tf }}
            onClick={onPick}
            onKeyDown={onKeyDown}
            className={ITEM}
          >
            <span className="w-20 shrink-0 font-mono">{item.symbol}</span>
            <span className="truncate text-muted-foreground">{item.name}</span>
            <span className="ml-auto shrink-0 text-xs text-muted-foreground">{item.market}</span>
          </Link>
        </li>
      ))}
      <li>
        <Link to="/" search={{ q }} onClick={onPick} onKeyDown={onKeyDown} className={`${ITEM} text-muted-foreground`}>
          All results for “{q}”
        </Link>
      </li>
    </ul>
  );
}

// The header search's state: the text, whether the list is open, and its handlers.
function useQuickSearch() {
  const [text, setText] = useState('');
  const [open, setOpen] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const q = useDebouncedValue(text.trim(), DEBOUNCE_MS);
  const result = useQuery({ ...instrumentSearchQueryOptions({ q, limit: LIMIT, offset: 0 }), enabled: q !== '' });

  const onPick = () => {
    setOpen(false);
    setText('');
    input.current?.blur();
  };
  // The list stays open while the focus moves between the input and its links.
  const onBlur = (event: FocusEvent<HTMLDivElement>) => {
    if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
  };
  // ArrowDown goes into the list; Enter opens the first result.
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    const first = event.currentTarget.parentElement?.querySelector('a');
    if (event.key === 'Escape') setOpen(false);
    if ((event.key === 'ArrowDown' || event.key === 'Enter') && first) {
      event.preventDefault();
      if (event.key === 'Enter') first.click();
      else first.focus();
    }
  };
  // Clearing the box (Escape does that in a search input) closes the list at once.
  const onChange = (value: string) => {
    setText(value);
    setOpen(value.trim() !== '');
  };
  return {
    text,
    q,
    open: open && q !== '',
    result,
    input,
    onPick,
    onBlur,
    onKeyDown,
    onChange,
    show: () => setOpen(true),
  };
}

// Search from any instrument page: type "eth", pick one with the mouse or the arrow keys and
// Enter, and its chart opens in the same timeframe.
export function QuickSearch() {
  const { text, q, open, result, input, onPick, onBlur, onKeyDown, onChange, show } = useQuickSearch();
  const tf = useRouterState({ select: (state) => (state.location.search as { tf?: string }).tf });

  return (
    <div className="relative w-full max-w-xs" onBlur={onBlur}>
      <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
      <input
        ref={input}
        type="search"
        aria-label="Go to an instrument"
        value={text}
        maxLength={50}
        placeholder="Search…"
        onChange={(event) => onChange(event.target.value)}
        onFocus={show}
        onKeyDown={onKeyDown}
        className="h-8 w-full rounded-md border bg-background pr-2 pl-8 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
      />
      {open && (
        <Results
          q={q}
          items={result.data?.items ?? []}
          pending={result.isPending}
          tf={tf}
          input={input}
          onPick={onPick}
        />
      )}
    </div>
  );
}

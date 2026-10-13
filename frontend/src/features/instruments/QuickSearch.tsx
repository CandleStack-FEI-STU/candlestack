import { useQuery } from '@tanstack/react-query';
import { Link, useRouterState } from '@tanstack/react-router';
import { Search } from 'lucide-react';
import {
  useRef,
  useState,
  type FocusEvent,
  type KeyboardEvent,
  type MouseEvent,
  type ReactNode,
  type RefObject,
} from 'react';

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

// Safari and Firefox on macOS blur the input on mousedown with no relatedTarget, which would
// close the list before the click lands. Keeping the focus where it is lets the click through.
const keepFocus = (event: MouseEvent) => event.preventDefault();

// A Ctrl/Cmd-, Shift- or Alt-click opens the result elsewhere: this tab keeps its search.
const opensElsewhere = (event: MouseEvent) =>
  event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0;

// What the list says above its links: searching, an error, or that nothing matched.
type ResultsState = { searching: boolean; error: Error | null; items: readonly Instrument[] };

function StatusItem({ tone = 'muted', children }: { tone?: 'muted' | 'error'; children: ReactNode }) {
  const color = tone === 'error' ? 'text-destructive' : 'text-muted-foreground';
  return <li className={`px-3 py-1.5 ${color}`}>{children}</li>;
}

function StatusNote({ searching, error, items }: ResultsState) {
  if (searching) return <StatusItem>Searching…</StatusItem>;
  if (error) return <StatusItem tone="error">Search failed: {error.message}</StatusItem>;
  if (items.length === 0) return <StatusItem>No instruments match.</StatusItem>;
  return null;
}

type ResultsProps = ResultsState & {
  q: string;
  tf: string | undefined;
  input: RefObject<HTMLInputElement | null>;
  onPick: () => void;
};

function Results({ q, tf, input, onPick, ...state }: ResultsProps) {
  const onKeyDown = (event: KeyboardEvent<HTMLAnchorElement>) => onListKey(event, input);
  const onClick = (event: MouseEvent) => {
    if (!opensElsewhere(event)) onPick();
  };
  const link = { onClick, onKeyDown, onMouseDown: keepFocus };
  return (
    <ul className="absolute top-full right-0 z-20 mt-1 w-full max-w-[calc(100vw-2rem)] min-w-72 overflow-hidden rounded-md border bg-background py-1 text-sm shadow-lg">
      <StatusNote {...state} />
      {state.items.map((item) => (
        <li key={item.id}>
          <Link to="/instrument/$id" params={{ id: item.id }} search={{ tf }} {...link} data-result className={ITEM}>
            <span className="w-20 shrink-0 font-mono">{item.symbol}</span>
            <span className="truncate text-muted-foreground">{item.name}</span>
            <span className="ml-auto shrink-0 text-xs text-muted-foreground">{item.market}</span>
          </Link>
        </li>
      ))}
      <li>
        <Link to="/" search={{ q }} {...link} className={`${ITEM} text-muted-foreground`}>
          All results for “{q}”
        </Link>
      </li>
    </ul>
  );
}

// The results for what is in the box, never the previous query's: while the typing has not
// settled, the first answer is on its way, or the previous answer stands in for the new one
// (keepPreviousData), the list says "Searching…" and shows no rows.
function useResults(text: string) {
  const q = useDebouncedValue(text.trim(), DEBOUNCE_MS);
  const result = useQuery({ ...instrumentSearchQueryOptions({ q, limit: LIMIT, offset: 0 }), enabled: q !== '' });
  const searching = text.trim() !== q || result.isPending || result.isPlaceholderData;
  return {
    q,
    searching,
    error: searching ? null : result.error,
    items: searching ? [] : (result.data?.items ?? []),
  };
}

// The header search's state: the text, whether the list is open, and its handlers.
function useQuickSearch() {
  const [text, setText] = useState('');
  const [open, setOpen] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const results = useResults(text);

  const onPick = () => {
    setOpen(false);
    setText('');
    input.current?.blur();
  };
  // The list stays open while the focus moves between the input and its links.
  const onBlur = (event: FocusEvent<HTMLDivElement>) => {
    if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
  };
  // ArrowDown goes into the list. Enter opens the first instrument and nothing else: not "All
  // results" when nothing matched or the search failed, and not a row while still searching.
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape') return setOpen(false);
    if (event.key !== 'ArrowDown' && event.key !== 'Enter') return;
    event.preventDefault();
    const list = event.currentTarget.parentElement;
    if (event.key === 'ArrowDown') list?.querySelector('a')?.focus();
    else if (!results.searching) list?.querySelector<HTMLAnchorElement>('a[data-result]')?.click();
  };
  // Clearing the box (Escape does that in a search input) closes the list at once.
  const onChange = (value: string) => {
    setText(value);
    setOpen(value.trim() !== '');
  };
  return { text, results, open: open && results.q !== '', input, onPick, onBlur, onKeyDown, onChange, setOpen };
}

// Search from any instrument page: type "eth", pick one with the mouse or the arrow keys and
// Enter, and its chart opens in the same timeframe.
export function QuickSearch() {
  const { text, results, open, input, onPick, onBlur, onKeyDown, onChange, setOpen } = useQuickSearch();
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
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        className="h-8 w-full rounded-md border bg-background pr-2 pl-8 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
      />
      {open && <Results {...results} tf={tf} input={input} onPick={onPick} />}
    </div>
  );
}

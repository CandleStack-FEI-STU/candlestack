/* oxlint-disable jsx-a11y/prefer-tag-over-role -- a native <select> cannot show two sections,
   group labels or why an entry is disabled: the lists are built from the ARIA listbox roles. */
import { useNavigate } from '@tanstack/react-router';
import { Check, ChevronDown, SlidersHorizontal } from 'lucide-react';
import { useId, useRef, useState, type KeyboardEvent, type ReactNode, type RefObject } from 'react';

import type { Exchange, Market } from '@/api';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';

import {
  applyOption,
  canPick,
  filterOptions,
  filtersSummary,
  nextActive,
  optionGroup,
  usableActive,
  sectionStart,
  type FilterOption,
  type OptionGroup,
} from './filterRules';

type Props = { market: Market | undefined; exchange: Exchange | undefined };

type OptionProps = {
  option: FilterOption;
  index: number;
  active: number;
  onPick: () => void;
  onFocus: () => void;
  onKeyDown: (event: KeyboardEvent) => void;
};

// One entry: its name, why it cannot be picked ("Stocks only"), and a check when it is chosen.
// The focus moves through the entries (one tab stop); the pointer moves it too, so mouse and
// keyboard highlight the same entry.
function Option({ option, index, active, onPick, onFocus, onKeyDown }: OptionProps) {
  const usable = canPick(option);
  return (
    <div
      role="option"
      data-index={index}
      tabIndex={index === active ? 0 : -1}
      aria-selected={option.selected}
      aria-disabled={!usable || undefined}
      // A click or a tap also moves the focus there (a tap sends no pointermove), so the arrows go
      // on from the entry picked.
      onClick={
        usable
          ? () => {
              onFocus();
              onPick();
            }
          : undefined
      }
      onKeyDown={onKeyDown}
      onMouseDown={(event) => !usable && event.preventDefault()}
      onPointerMove={() => usable && index !== active && onFocus()}
      className={cn(
        'flex h-8 cursor-default items-center gap-2 rounded-sm px-2 whitespace-nowrap outline-none select-none focus:bg-accent',
        !usable && 'cursor-not-allowed text-muted-foreground',
      )}
    >
      <span>{option.label}</span>
      <span className="ml-auto text-xs text-muted-foreground">{option.section === 'exchange' && option.reason}</span>
      <Check aria-hidden className={cn('text-primary', !option.selected && 'invisible')} />
    </div>
  );
}

function Group({ label, children }: { label: string; children: ReactNode }) {
  const id = useId();
  return (
    <>
      <div aria-hidden className="-mx-1 my-1 h-px bg-border" />
      <div role="group" aria-labelledby={id}>
        <div id={id} className="flex h-7 items-end px-2 pb-1 text-xs font-medium text-muted-foreground select-none">
          {label}
        </div>
        {children}
      </div>
    </>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  const id = useId();
  return (
    <div>
      <p id={id} className="mb-2 text-xs font-medium text-muted-foreground">
        {title}
      </p>
      <div role="listbox" aria-labelledby={id} className="-mx-1">
        {children}
      </div>
    </div>
  );
}

type SectionsProps = { options: FilterOption[]; render: (option: FilterOption, index: number) => ReactNode };

// The two sections side by side (Type 128 px, Exchange the rest of 412 px); stacked on phones.
function Sections({ options, render }: SectionsProps) {
  const group = (name: OptionGroup) =>
    options.flatMap((option, index) => (optionGroup(option) === name ? [render(option, index)] : []));
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-[128px_minmax(0,1fr)] sm:gap-4">
      <Section title="Type">{group('type')}</Section>
      <Section title="Exchange">
        {group('all-exchanges')}
        <Group label="Stock exchanges">{group('stock')}</Group>
        <Group label="Crypto exchanges">{group('crypto')}</Group>
      </Section>
    </div>
  );
}

// The panel's state: open or not, the entry with the focus, and what a pick or a key does. A pick
// goes to the URL (page 1, a new history entry, so Back undoes it) and leaves the panel open for
// the second filter; Tab closes it like Escape does. The entry with the focus is never one the
// type has just disabled.
function useFiltersPanel(options: FilterOption[]) {
  const navigate = useNavigate({ from: '/' });
  const [open, setOpen] = useState(false);
  const [focused, setActive] = useState(0);
  const active = usableActive(options, focused);
  const panel = useRef<HTMLDivElement>(null);

  const focus = (index: number) => {
    setActive(index);
    panel.current?.querySelector<HTMLElement>(`[data-index="${index}"]`)?.focus();
  };
  const pick = (option: FilterOption | undefined) => {
    if (!option || option.selected || !canPick(option)) return;
    void navigate({ search: (prev) => applyOption(prev, option) });
  };
  const onKeyDown = (event: KeyboardEvent) => {
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key === 'Tab' || event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      return event.key === 'Tab' ? setOpen(false) : pick(options[active]);
    }
    const next = nextActive(options, active, event.key);
    if (next === undefined) return;
    event.preventDefault();
    focus(next);
  };
  return { open, setOpen, active, panel, focus, pick, onKeyDown };
}

type TriggerProps = { summary: string; onOpen: () => void; ref: RefObject<HTMLButtonElement | null> };

// The button: the summary between the filter icon and the chevron. ArrowDown opens it too.
function Trigger({ summary, onOpen, ref }: TriggerProps) {
  return (
    <PopoverTrigger
      ref={ref}
      aria-label={`Filters: ${summary}`}
      onKeyDown={(event) => {
        if (event.key !== 'ArrowDown') return;
        event.preventDefault();
        onOpen();
      }}
      className="group flex h-[34px] w-[200px] shrink-0 items-center gap-2 rounded-md border bg-background pr-2.5 pl-3 text-left text-sm text-muted-foreground transition-[color,border-color,box-shadow] outline-none hover:text-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 data-[state=open]:border-ring data-[state=open]:text-foreground"
    >
      <SlidersHorizontal aria-hidden className="size-4 shrink-0" />
      <span className="min-w-0 flex-1 truncate text-foreground">{summary}</span>
      <ChevronDown
        aria-hidden
        className="size-4 shrink-0 text-muted-foreground transition-transform group-data-[state=open]:rotate-180"
      />
    </PopoverTrigger>
  );
}

// Type and exchange behind one button of a fixed size (34 × 200 px) that sums them up, so nothing
// in the row moves when they change (#182). The panel opens on Enter, Space or ArrowDown and starts
// on the chosen type; Escape, Tab or a click outside closes it.
export function Filters({ market, exchange }: Props) {
  const options = filterOptions(market, exchange);
  const summary = filtersSummary(market, exchange);
  const { open, setOpen, active, panel, focus, pick, onKeyDown } = useFiltersPanel(options);
  const trigger = useRef<HTMLButtonElement>(null);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <Trigger ref={trigger} summary={summary} onOpen={() => setOpen(true)} />
      <PopoverContent
        ref={panel}
        aria-label="Filters"
        align="end"
        collisionPadding={16}
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          focus(sectionStart(options, 'type'));
        }}
        // A click on the padding or a heading would focus the panel itself, where no key works:
        // the focus goes on to the entry instead.
        onFocus={(event) => event.target === event.currentTarget && focus(active)}
        // Back to the button, unless a click outside put the focus somewhere else.
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          if (document.activeElement === document.body) trigger.current?.focus();
        }}
        className="max-h-[480px] w-[calc(100vw-2rem)] overflow-y-auto rounded-lg p-3 text-sm sm:w-[412px]"
      >
        <Sections
          options={options}
          render={(option, index) => (
            <Option
              key={index}
              {...{ option, index, active, onKeyDown }}
              onPick={() => pick(option)}
              onFocus={() => focus(index)}
            />
          )}
        />
      </PopoverContent>
    </Popover>
  );
}

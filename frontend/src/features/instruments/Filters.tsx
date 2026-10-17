/* oxlint-disable jsx-a11y/prefer-tag-over-role -- a native <select> cannot show two sections,
   group labels or why an entry is disabled: the lists are built from the ARIA listbox roles. */
import { useNavigate } from '@tanstack/react-router';
import { Check, ChevronDown, SlidersHorizontal } from 'lucide-react';
import { useId, useRef, useState, type KeyboardEvent, type ReactNode, type RefObject } from 'react';

import type { Exchange, Market } from '@/api';
import { DROPDOWN_CHEVRON, DROPDOWN_TRIGGER } from '@/components/buttonStyles';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { cn } from '@/lib/utils';
import type { ListSort } from '@/routes/instrumentsSearch';

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

type Props = { market: Market | undefined; exchange: Exchange | undefined; sort?: ListSort | undefined };

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

// On a phone the panel is tightened so that every entry fits in its 480 px without scrolling:
// group labels 24 px high, 2 px around the separators, headings 4 px above their list.
function Group({ label, children }: { label: string; children: ReactNode }) {
  const id = useId();
  return (
    <>
      <div aria-hidden className="-mx-1 my-0.5 h-px bg-border sm:my-1" />
      <div role="group" aria-labelledby={id}>
        <div
          id={id}
          className="flex h-6 items-end px-2 pb-1 text-xs font-medium text-muted-foreground select-none sm:h-7"
        >
          {label}
        </div>
        {children}
      </div>
    </>
  );
}

function Section({ title, area, children }: { title: string; area: string; children: ReactNode }) {
  const id = useId();
  return (
    <div className={area}>
      <p id={id} className="mb-1 text-xs font-medium text-muted-foreground sm:mb-2">
        {title}
      </p>
      <div role="listbox" aria-labelledby={id} className="-mx-1">
        {children}
      </div>
    </div>
  );
}

type SectionsProps = { options: FilterOption[]; render: (option: FilterOption, index: number) => ReactNode };

// Type over Sort by in the 128 px left column, Exchange the rest of 412 px on the right; on a
// phone Type and Sort by side by side, Exchange below them.
function Sections({ options, render }: SectionsProps) {
  const group = (name: OptionGroup) =>
    options.flatMap((option, index) => (optionGroup(option) === name ? [render(option, index)] : []));
  return (
    <div className="grid grid-cols-2 gap-2 [grid-template-areas:'type_sort'_'exchange_exchange'] sm:grid-cols-[128px_minmax(0,1fr)] sm:grid-rows-[auto_1fr] sm:gap-4 sm:[grid-template-areas:'type_exchange'_'sort_exchange']">
      <Section title="Type" area="[grid-area:type]">
        {group('type')}
      </Section>
      <Section title="Sort by" area="[grid-area:sort]">
        {group('sort')}
      </Section>
      <Section title="Exchange" area="[grid-area:exchange]">
        {group('all-exchanges')}
        <Group label="Stock exchanges">{group('stock')}</Group>
        <Group label="Crypto exchanges">{group('crypto')}</Group>
      </Section>
    </div>
  );
}

// The panel's state: open or not, the entry with the focus, and what a pick or a key does. A pick
// goes to the URL (page 1, a new history entry, so Back undoes it) and leaves the panel open for
// the second filter. The entry with the focus is never one the type has just disabled.
function useFiltersPanel(options: FilterOption[]) {
  const navigate = useNavigate({ from: '/instruments' });
  // The arrows follow the layout, which changes at sm (640 px).
  const layout = useMediaQuery('(min-width: 640px)') ? 'wide' : 'phone';
  const [open, setOpen] = useState(false);
  const [focused, setActive] = useState(0);
  const active = usableActive(options, focused);
  const trigger = useRef<HTMLButtonElement>(null);
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
    // Tab and Shift+Tab leave the panel as they leave the button: the focus goes to the button,
    // and the browser moves it on from there to the next or previous element of the page (the
    // panel itself sits at the end of the page, in a portal).
    if (event.key === 'Tab') {
      trigger.current?.focus();
      return setOpen(false);
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      return pick(options[active]);
    }
    const next = nextActive(options, active, event.key, layout);
    if (next === undefined) return;
    event.preventDefault();
    focus(next);
  };
  return { open, setOpen, active, trigger, panel, focus, pick, onKeyDown };
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
      className={cn(DROPDOWN_TRIGGER, 'w-[200px] shrink-0')}
    >
      <SlidersHorizontal aria-hidden className="size-4 shrink-0" />
      <span className="min-w-0 flex-1 truncate text-foreground">{summary}</span>
      <ChevronDown aria-hidden className={DROPDOWN_CHEVRON} />
    </PopoverTrigger>
  );
}

// Type, order and exchange behind one button of a fixed size (34 × 200 px) that sums them up, so
// nothing in the row moves when they change (#182, #184). The panel opens on Enter, Space or
// ArrowDown and starts on the chosen type. Escape closes it and the focus goes back to the button;
// Tab and Shift+Tab close it and move on to the element after or before the button; so does a
// click outside.
export function Filters({ market, exchange, sort }: Props) {
  const options = filterOptions(market, exchange, sort);
  const summary = filtersSummary(market, exchange, sort);
  const { open, setOpen, active, trigger, panel, focus, pick, onKeyDown } = useFiltersPanel(options);

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
        // Back to the button (Escape), unless Tab or a click outside put the focus somewhere else.
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          if (document.activeElement === document.body) trigger.current?.focus();
        }}
        className="max-h-[480px] w-[calc(100vw-2rem)] overflow-y-auto rounded-lg p-2 text-sm sm:w-[412px] sm:p-3"
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

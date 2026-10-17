/* oxlint-disable jsx-a11y/prefer-tag-over-role -- a native <select> cannot show two sections,
   group labels, counts or why an entry is disabled: the lists are built from the ARIA listbox
   roles. */
import { Check, ChevronDown, SlidersHorizontal } from 'lucide-react';
import { useId, useRef, useState, type FocusEvent, type KeyboardEvent, type ReactNode, type RefObject } from 'react';

import { DROPDOWN_CHEVRON, DROPDOWN_TRIGGER } from '@/components/buttonStyles';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';

// The Filters button and its panel (mockups/app, .fp-t and .fp), on the instrument list and the
// backtests: a button of a fixed size (34 × 200 px) that sums the filters up, so nothing in the
// row moves when they change, over a panel of sections of entries. Each list says what its
// entries are, how the arrows move between them and what a pick does.

type Entry = { selected: boolean };

// How an entry is lit: whenever it has the focus, also right after the panel opened by a click on
// its button (the instrument list's design); or only under the pointer and, once the keyboard is in
// use (data-keys on the panel), where the focus is (mockups/app .fp-o, the backtests).
export const FOCUS_HIGHLIGHT = 'focus:bg-accent';
export const HOVER_HIGHLIGHT = 'hover:bg-accent in-data-keys:focus:bg-accent';

// Whether the panel is used with the keyboard: a key on the button or in the panel says so, a press
// of the pointer on the button says not. The browser's own :focus-visible cannot tell, as the focus
// moves into the panel by script.
function useKeyboardUse() {
  const [keys, setKeys] = useState(false);
  const fromKeys = () => setKeys(true);
  return {
    trigger: { onPointerDown: () => setKeys(false), onKeyDownCapture: fromKeys },
    panel: { 'data-keys': keys || undefined, onKeyDownCapture: fromKeys },
  };
}

type OptionProps = {
  index: number;
  active: number;
  selected: boolean;
  usable: boolean;
  label: ReactNode;
  note: ReactNode;
  highlight: string;
  onPick: () => void;
  onFocus: () => void;
  onKeyDown: (event: KeyboardEvent) => void;
};

// One entry: its name, a note at the right (a count, why it cannot be picked), and a check when
// it is chosen. The focus moves through the entries (one tab stop); the pointer moves it too, so
// mouse and keyboard highlight the same entry.
function Option({ index, active, selected, usable, label, note, highlight, onPick, onFocus, onKeyDown }: OptionProps) {
  return (
    <div
      role="option"
      data-index={index}
      tabIndex={index === active ? 0 : -1}
      aria-selected={selected}
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
        'flex h-8 cursor-default items-center gap-2 rounded-sm px-2 whitespace-nowrap outline-none select-none',
        highlight,
        !usable && 'cursor-not-allowed text-muted-foreground',
      )}
    >
      <span className="min-w-0 truncate">{label}</span>
      <span className="ml-auto shrink-0 text-xs/[1.5] text-muted-foreground">{note}</span>
      <Check aria-hidden className={cn('size-4 shrink-0 text-primary', !selected && 'invisible')} />
    </div>
  );
}

type SectionProps = {
  title: string;
  area?: string;
  // The space under the heading: 4 px on a phone and 8 px from sm up unless a panel says otherwise.
  headingClassName?: string;
  children: ReactNode;
};

// A section of the panel: its heading over its list of entries.
export function FilterSection({ title, area, headingClassName = 'mb-1 sm:mb-2', children }: SectionProps) {
  const id = useId();
  return (
    <div className={area}>
      <p id={id} className={cn('text-xs font-medium text-muted-foreground', headingClassName)}>
        {title}
      </p>
      <div role="listbox" aria-labelledby={id} className="-mx-1">
        {children}
      </div>
    </div>
  );
}

type TriggerProps = {
  summary: string;
  openBorder: string;
  input: ReturnType<typeof useKeyboardUse>['trigger'];
  onOpen: (open: true) => void;
  ref: RefObject<HTMLButtonElement | null>;
};

// The button: the summary between the filter icon and the chevron. ArrowDown opens it too.
function Trigger({ summary, openBorder, input, onOpen, ref }: TriggerProps) {
  return (
    <PopoverTrigger
      ref={ref}
      {...input}
      aria-label={`Filters: ${summary}`}
      onKeyDown={(event) => {
        if (event.key !== 'ArrowDown') return;
        event.preventDefault();
        onOpen(true);
      }}
      className={cn(DROPDOWN_TRIGGER, 'w-[200px] shrink-0', openBorder)}
    >
      <SlidersHorizontal aria-hidden className="size-4 shrink-0" />
      <span className="min-w-0 flex-1 truncate text-foreground">{summary}</span>
      <ChevronDown aria-hidden className={DROPDOWN_CHEVRON} />
    </PopoverTrigger>
  );
}

type Rules<T extends Entry> = {
  options: readonly T[];
  // Whether an entry can be picked; every entry when left out.
  canPick?: ((option: T) => boolean) | undefined;
  // The entry to keep the focus on when the one it is on cannot be picked any more.
  usable?: ((focused: number) => number) | undefined;
  // Which entry gets the focus after a key press, or undefined when the key does not move it.
  move: (active: number, key: string) => number | undefined;
  onPick: (option: T) => void;
};

// The panel's state: open or not, the entry with the focus, and what a pick or a key does. A pick
// leaves the panel open for the next filter.
function usePanel<T extends Entry>({
  options,
  canPick = () => true,
  usable = (index) => index,
  move,
  onPick,
}: Rules<T>) {
  const [open, setOpen] = useState(false);
  const [focused, setFocused] = useState(0);
  const active = usable(focused);
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);

  const focus = (index: number) => {
    setFocused(index);
    panel.current?.querySelector<HTMLElement>(`[data-index="${index}"]`)?.focus();
  };
  const pick = (option: T | undefined) => {
    if (option && !option.selected && canPick(option)) onPick(option);
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
    const next = move(active, event.key);
    if (next === undefined) return;
    event.preventDefault();
    focus(next);
  };
  return { open, setOpen, active, trigger, panel, focus, pick, onKeyDown, canPick };
}

type Panel<T extends Entry> = ReturnType<typeof usePanel<T>>;

// The panel's own handlers. The focus goes to `start` when it opens. A click on the padding or a
// heading would focus the panel itself, where no key works: the focus goes on to the entry
// instead. On closing it goes back to the button (Escape), unless Tab or a click outside put it
// somewhere else.
function useContentProps<T extends Entry>({ panel, trigger, focus, active }: Panel<T>, start: () => number) {
  return {
    ref: panel,
    onOpenAutoFocus: (event: Event) => {
      event.preventDefault();
      focus(start());
    },
    onFocus: (event: FocusEvent) => event.target === event.currentTarget && focus(active),
    onCloseAutoFocus: (event: Event) => {
      event.preventDefault();
      if (document.activeElement === document.body) trigger.current?.focus();
    },
  };
}

// What each entry needs from the panel.
function useEntryProps<T extends Entry>({ active, canPick, onKeyDown, pick, focus }: Panel<T>, highlight: string) {
  return (option: T, index: number) => ({
    index,
    highlight,
    active,
    selected: option.selected,
    usable: canPick(option),
    onKeyDown,
    onPick: () => pick(option),
    onFocus: () => focus(index),
  });
}

type Props<T extends Entry> = Rules<T> & {
  summary: string;
  // Where the focus goes when the panel opens: the chosen entry of its first section.
  start: () => number;
  label: (option: T) => ReactNode;
  note?: (option: T) => ReactNode;
  // Which edge of the button the panel lines up with.
  align: 'start' | 'end';
  // How far below the button the panel opens, in px.
  sideOffset: number;
  // The button's border while the panel is open, as its design colours it.
  openBorder: string;
  // Which entry is lit: the one with the focus (FOCUS_HIGHLIGHT), or the one under the pointer and the one the keyboard moved to (HOVER_HIGHLIGHT), as the panel's design shows it.
  highlight: string;
  // The panel's size and padding.
  className: string;
  // The sections, each given the entries it shows through `render`.
  children: (render: (option: T, index: number) => ReactNode) => ReactNode;
};

// The panel opens on Enter, Space or ArrowDown and starts on `start`. Escape closes it and the
// focus goes back to the button; Tab and Shift+Tab close it and move on to the element after or
// before the button; so does a click outside.
export function FiltersPopover<T extends Entry>({
  summary,
  start,
  label,
  note,
  align,
  sideOffset,
  openBorder,
  className,
  children,
  ...rules
}: Props<T>) {
  const state = usePanel(rules);
  const content = useContentProps(state, start);
  const entry = useEntryProps(state, rules.highlight);
  const { open, setOpen, trigger } = state;
  const input = useKeyboardUse();
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <Trigger ref={trigger} summary={summary} openBorder={openBorder} input={input.trigger} onOpen={setOpen} />
      <PopoverContent
        {...content}
        {...input.panel}
        aria-label="Filters"
        align={align}
        sideOffset={sideOffset}
        collisionPadding={16}
        className={cn('rounded-lg text-sm', className)}
      >
        {children((option, index) => (
          <Option key={index} {...entry(option, index)} label={label(option)} note={note?.(option)} />
        ))}
      </PopoverContent>
    </Popover>
  );
}

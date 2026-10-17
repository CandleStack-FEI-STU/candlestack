/* oxlint-disable jsx-a11y/prefer-tag-over-role -- the exchanges are grouped by the ARIA group
   role inside the panel's listbox. */
import { useNavigate } from '@tanstack/react-router';
import { useId, type ReactNode } from 'react';

import type { Exchange, Market } from '@/api';
import { FOCUS_HIGHLIGHT, FilterSection, FiltersPopover } from '@/components/FiltersPopover';
import { useMediaQuery } from '@/lib/useMediaQuery';
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

type SectionsProps = { options: FilterOption[]; render: (option: FilterOption, index: number) => ReactNode };

// Type over Sort by in the 128 px left column, Exchange the rest of 412 px on the right; on a
// phone Type and Sort by side by side, Exchange below them.
function Sections({ options, render }: SectionsProps) {
  const group = (name: OptionGroup) =>
    options.flatMap((option, index) => (optionGroup(option) === name ? [render(option, index)] : []));
  return (
    <div className="grid grid-cols-2 gap-2 [grid-template-areas:'type_sort'_'exchange_exchange'] sm:grid-cols-[128px_minmax(0,1fr)] sm:grid-rows-[auto_1fr] sm:gap-4 sm:[grid-template-areas:'type_exchange'_'sort_exchange']">
      <FilterSection title="Type" area="[grid-area:type]">
        {group('type')}
      </FilterSection>
      <FilterSection title="Sort by" area="[grid-area:sort]">
        {group('sort')}
      </FilterSection>
      <FilterSection title="Exchange" area="[grid-area:exchange]">
        {group('all-exchanges')}
        <Group label="Stock exchanges">{group('stock')}</Group>
        <Group label="Crypto exchanges">{group('crypto')}</Group>
      </FilterSection>
    </div>
  );
}

// Type, order and exchange behind one button (#182, #184). A pick goes to the URL (page 1, a new
// history entry, so Back undoes it). The panel starts on the chosen type; the entry with the focus
// is never one the type has just disabled.
export function Filters({ market, exchange, sort }: Props) {
  const navigate = useNavigate({ from: '/instruments' });
  // The arrows follow the layout, which changes at sm (640 px).
  const layout = useMediaQuery('(min-width: 640px)') ? 'wide' : 'phone';
  const options = filterOptions(market, exchange, sort);
  return (
    <FiltersPopover
      summary={filtersSummary(market, exchange, sort)}
      options={options}
      canPick={canPick}
      usable={(focused) => usableActive(options, focused)}
      move={(active, key) => nextActive(options, active, key, layout)}
      onPick={(option) => void navigate({ search: (prev) => applyOption(prev, option) })}
      start={() => sectionStart(options, 'type')}
      label={(option) => option.label}
      note={(option) => option.section === 'exchange' && option.reason}
      align="end"
      sideOffset={4}
      openBorder="data-[state=open]:border-ring"
      highlight={FOCUS_HIGHLIGHT}
      className="max-h-[480px] w-[calc(100vw-2rem)] overflow-y-auto p-2 sm:w-[412px] sm:p-3"
    >
      {(render) => <Sections options={options} render={render} />}
    </FiltersPopover>
  );
}

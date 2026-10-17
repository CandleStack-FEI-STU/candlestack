import { useNavigate } from '@tanstack/react-router';
import type { ReactNode } from 'react';

import type { BacktestsPage } from '@/api';
import { FilterSection, FiltersPopover } from '@/components/FiltersPopover';
import type { BacktestsSearch } from '@/routes/backtestsSearch';

import { applyOption, filterOptions, filtersSummary, nextActive, sectionStart, type FilterOption } from './filterRules';
import { ModelName } from './parts';

type Props = { search: BacktestsSearch; page: Pick<BacktestsPage, 'counts' | 'models'> };

// Show and Model behind one button (mockups/app, btFilters), the panel lined up with the button's
// left edge: Show in its 128 px column, the models beside it with their framework's mark. A pick
// goes to the URL (page 1, a new history entry, so Back undoes it) and leaves the panel open.
export function BacktestFilters({ search, page }: Props) {
  const navigate = useNavigate({ from: '/backtests' });
  const options = filterOptions(search, page);
  const section = (name: FilterOption['section'], render: (option: FilterOption, index: number) => ReactNode) =>
    options.flatMap((option, index) => (option.section === name ? [render(option, index)] : []));
  return (
    <FiltersPopover
      summary={filtersSummary(search)}
      options={options}
      move={(active, key) => nextActive(options, active, key)}
      onPick={(option) => void navigate({ search: (prev) => applyOption(prev, option) })}
      start={() => sectionStart(options, 'show')}
      label={(option) =>
        option.section === 'model' && option.framework ? (
          <ModelName name={option.label} framework={option.framework} />
        ) : (
          option.label
        )
      }
      note={(option) => option.count}
      align="start"
      sideOffset={6}
      openBorder="data-[state=open]:border-[color-mix(in_srgb,var(--accent)_55%,var(--rule))]"
      className="w-[min(412px,calc(100vw-2rem))] p-3 shadow-[0_10px_28px_var(--shadow)]"
    >
      {(render) => (
        <div className="grid grid-cols-[128px_minmax(0,1fr)] gap-4">
          <FilterSection title="Show">{section('show', render)}</FilterSection>
          <FilterSection title="Model">{section('model', render)}</FilterSection>
        </div>
      )}
    </FiltersPopover>
  );
}

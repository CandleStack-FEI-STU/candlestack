import type { Backtest } from '@/api';
import { StarButton } from '@/components/StarButton';
import { useDateStyle } from '@/features/preferences';
import { formatRecentTime } from '@/lib/dates';
import { formatCount, formatPercent, formatSharpe } from '@/lib/results';
import { cn } from '@/lib/utils';
import type { BacktestsColumn, BacktestsSearch } from '@/routes/backtestsSearch';

import { BacktestNumber, FailedBadge, InstrumentChips, Missing, ModelName, ReturnValue } from './parts';
import { CELL, HEAD, NUMBER, ROW, RowOpener, SortButton, TABLE } from './table';

// The columns (mockups/app, BT_COLS) and from which width down each one hides, so the table never
// scrolls sideways: Trades at 1100 px, Max drawdown at 1060, When at 760, Model at 560, Sharpe at
// 420. Instruments does not sort.
const COLUMNS: readonly { label: string; sort?: BacktestsColumn; hide?: string; number?: boolean }[] = [
  { label: 'Backtest', sort: 'number' },
  { label: 'Instruments' },
  { label: 'Model', sort: 'model', hide: 'max-[560px]:hidden' },
  { label: 'Return', sort: 'return', number: true },
  { label: 'Sharpe', sort: 'sharpe', hide: 'max-[420px]:hidden', number: true },
  { label: 'Max drawdown', sort: 'max_drawdown', hide: 'max-[1060px]:hidden', number: true },
  { label: 'Trades', sort: 'trades', hide: 'max-[1100px]:hidden', number: true },
  { label: 'When', sort: 'when', hide: 'max-[760px]:hidden' },
];
const hideOf = (label: string) => COLUMNS.find((column) => column.label === label)?.hide;

type HeaderProps = { search: BacktestsSearch; onSort: (column: BacktestsColumn) => void };

// The headers; a click sorts by the column (withSortBy), the sorted one ink with ↓ or ↑.
function Header({ search, onSort }: HeaderProps) {
  return (
    <thead>
      <tr>
        {COLUMNS.map(({ label, sort, hide, number }) => {
          const on = sort !== undefined && search.sort === sort;
          const arrow = on ? (search.order === 'asc' ? ' ↑' : ' ↓') : '';
          return (
            <th
              key={label}
              scope="col"
              aria-sort={on ? (search.order === 'asc' ? 'ascending' : 'descending') : undefined}
              className={cn(HEAD, hide, number && 'text-right')}
            >
              {sort ? (
                <SortButton on={on} onClick={() => onSort(sort)}>
                  {label}
                  {arrow}
                </SortButton>
              ) : (
                label
              )}
            </th>
          );
        })}
      </tr>
    </thead>
  );
}

type RowProps = { backtest: Backtest; onOpen: (backtest: Backtest) => void; onStar: (backtest: Backtest) => void };

// A finished backtest shows its results; a failed one the Failed badge and dashes.
function Row({ backtest, onOpen, onStar }: RowProps) {
  const dateStyle = useDateStyle();
  const done = backtest.status === 'finished';
  const result = (text: string) => (done ? text : <Missing />);
  return (
    <tr className={ROW}>
      <td className={CELL}>
        <span className="inline-flex items-center gap-1.5">
          <StarButton
            starred={backtest.starred}
            label={`Star backtest ${backtest.number}`}
            onToggle={() => onStar(backtest)}
            className="relative z-10"
          />
          <RowOpener label={`Backtest #${backtest.number}`} onOpen={() => onOpen(backtest)}>
            <BacktestNumber backtest={backtest} />
          </RowOpener>
        </span>
      </td>
      <td className={CELL}>
        <InstrumentChips backtest={backtest} max={2} />
      </td>
      <td className={cn(CELL, hideOf('Model'))}>
        <ModelName name={backtest.model.name} framework={backtest.model.framework} />
      </td>
      <td className={cn(CELL, NUMBER)}>
        {done && backtest.total_return !== null ? <ReturnValue value={backtest.total_return} /> : <FailedBadge />}
      </td>
      <td className={cn(CELL, NUMBER, hideOf('Sharpe'))}>{result(formatSharpe(backtest.sharpe))}</td>
      <td className={cn(CELL, NUMBER, hideOf('Max drawdown'))}>{result(formatPercent(backtest.max_drawdown))}</td>
      <td className={cn(CELL, NUMBER, hideOf('Trades'))}>{result(formatCount(backtest.num_trades))}</td>
      <td className={cn(CELL, hideOf('When'), 'text-muted-foreground')}>
        {formatRecentTime(new Date(backtest.created_at), dateStyle)}
      </td>
    </tr>
  );
}

type Props = HeaderProps & {
  backtests: readonly Backtest[];
  // What the one row says when there are none: "No backtests match", or "No backtests yet".
  empty: string;
  onOpen: (backtest: Backtest) => void;
  onStar: (backtest: Backtest) => void;
};

// The Backtests page's table (mockups/app, btTable): the star and the number, the instruments as
// chips, the model by its mark, the results in mono at the right, and when it ran.
export function BacktestsTable({ backtests, empty, search, onSort, onOpen, onStar }: Props) {
  return (
    <table className={TABLE}>
      <Header search={search} onSort={onSort} />
      <tbody>
        {backtests.map((backtest) => (
          <Row key={backtest.id} backtest={backtest} onOpen={onOpen} onStar={onStar} />
        ))}
        {backtests.length === 0 && (
          <tr>
            <td colSpan={COLUMNS.length} className="p-6 text-center text-muted-foreground">
              {empty}
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}

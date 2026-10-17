import type { Backtest, Dashboard } from '@/api';
import { BacktestsIcon } from '@/components/icons';
import { DashboardCard } from '@/components/DashboardCard';
import {
  BacktestNumber,
  FailedBadge,
  InstrumentChips,
  RowOpener,
  RowStar,
  representationName,
  returnClass,
} from '@/features/backtests';
import { formatPercent, formatSharpe } from '@/lib/results';
import { cn } from '@/lib/utils';

import { Hint, MoreRow, STARRED_ROW, Sparkline } from './widgets';

type RowProps = { backtest: Backtest; onOpen: (backtest: Backtest) => void; onStar: (backtest: Backtest) => void };

// Two lines (.dd-sb): the star beside both; the number with up to two instruments, the small
// equity line and the return; under them the representation and the model, and the Sharpe ratio.
// A failed backtest has the Failed badge instead, without a line.
function Row({ backtest, onOpen, onStar }: RowProps) {
  const value = backtest.status === 'finished' ? backtest.total_return : null;
  return (
    <div className={cn(STARRED_ROW, 'grid-cols-[auto_minmax(0,1fr)_auto_auto] gap-y-px')}>
      <span className="row-span-2">
        <RowStar starred label={`Unstar backtest ${backtest.number}`} onToggle={() => onStar(backtest)} />
      </span>
      <span className="flex items-center gap-1.5 overflow-hidden text-[13px] text-ellipsis whitespace-nowrap">
        <RowOpener label={`Backtest #${backtest.number}`} onOpen={() => onOpen(backtest)}>
          <BacktestNumber backtest={backtest} />
        </RowOpener>
        <InstrumentChips backtest={backtest} max={2} tight />
      </span>
      {value !== null && backtest.equity ? <Sparkline equity={backtest.equity} /> : <span />}
      <span className="text-right font-mono text-sm font-semibold whitespace-nowrap">
        {value === null ? <FailedBadge /> : <span className={returnClass(value)}>{formatPercent(value)}</span>}
      </span>
      <span className="col-span-2 truncate text-xs text-muted-foreground">
        {representationName(backtest.representation)} · {backtest.model.name}
      </span>
      <span className="text-right font-mono text-[11px] whitespace-nowrap text-muted-foreground">
        {value !== null && backtest.sharpe !== null && `Sharpe ${formatSharpe(backtest.sharpe)}`}
      </span>
    </div>
  );
}

type Props = {
  starred: Dashboard['starred'];
  onOpen: (backtest: Backtest) => void;
  onStar: (backtest: Backtest) => void;
};

// The four starred backtests with the best Sharpe ratio (mockups/app, ddStarred), then More.
export function StarredBacktests({ starred, onOpen, onStar }: Props) {
  return (
    <DashboardCard icon={BacktestsIcon} title="Starred backtests" aside={<Hint>by Sharpe</Hint>} className="gap-0">
      {starred.backtests.length === 0 ? (
        <Hint>Star a backtest to keep it here.</Hint>
      ) : (
        <>
          <div className="flex flex-col">
            {starred.backtests.map((backtest) => (
              <Row key={backtest.id} backtest={backtest} onOpen={onOpen} onStar={onStar} />
            ))}
          </div>
          <MoreRow total={starred.total} to="/backtests" />
        </>
      )}
    </DashboardCard>
  );
}

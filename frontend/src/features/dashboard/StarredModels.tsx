import { Link } from '@tanstack/react-router';

import type { Model } from '@/api';
import { ModelsIcon } from '@/components/icons';
import { DashboardCard } from '@/components/DashboardCard';
import { RowStar } from '@/features/backtests';
import { formatShape, FrameworkTile, frameworkOf } from '@/features/models';
import { plural } from '@/lib/plural';
import { formatSharpe } from '@/lib/results';
import { cn } from '@/lib/utils';

import { starredModels } from './order';
import { Hint, MoreRow, STARRED_ROW, TOP } from './widgets';

// The framework's tile, the name over what it reads and its framework ("in 25×23 → 1 · Keras"),
// and at the right its best Sharpe ratio over how many backtests used it. The row opens the
// Models page.
function Row({ model, onStar }: { model: Model; onStar: (model: Model) => void }) {
  const framework = frameworkOf(model.framework);
  const name = framework ?? model.framework;
  const shape = formatShape(model.input_shape, model.output_shape);
  return (
    <div className={cn(STARRED_ROW, 'grid-cols-[auto_auto_minmax(0,1fr)_auto]')}>
      <RowStar starred label={`Unstar model ${model.name}`} onToggle={() => onStar(model)} />
      {framework && <FrameworkTile framework={framework} />}
      <span className={cn('flex min-w-0 flex-col', !framework && 'col-span-2')}>
        <Link
          to="/models"
          className="truncate text-[13px] font-medium outline-none after:absolute after:inset-0 focus-visible:text-primary"
        >
          {model.name}
        </Link>
        <span className="truncate font-mono text-[11.5px] text-muted-foreground">
          {shape === null ? name : `in ${shape} · ${name}`}
        </span>
      </span>
      <span className="flex flex-col items-end font-mono text-xs whitespace-nowrap">
        <b className="text-sm font-semibold">{formatSharpe(model.best_sharpe)}</b>
        <span className="text-[11px] text-muted-foreground">{plural(model.backtest_count, 'backtest')}</span>
      </span>
    </div>
  );
}

type Props = { models: readonly Model[]; onStar: (model: Model) => void };

// The four best starred models, then More to the Models page.
export function StarredModels({ models, onStar }: Props) {
  const starred = starredModels(models);
  return (
    <DashboardCard icon={ModelsIcon} title="Starred models" aside={<Hint>by best Sharpe</Hint>} className="gap-0">
      {starred.length === 0 ? (
        <Hint>Star a model to keep it here.</Hint>
      ) : (
        <>
          <div className="flex flex-col">
            {starred.slice(0, TOP).map((model) => (
              <Row key={model.id} model={model} onStar={onStar} />
            ))}
          </div>
          <MoreRow total={starred.length} to="/models" />
        </>
      )}
    </DashboardCard>
  );
}

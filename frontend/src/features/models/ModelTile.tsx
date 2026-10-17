import type { Model } from '@/api';
import { BUTTON_SIZES, GHOST_BUTTON } from '@/components/buttonStyles';
import { PencilIcon, TrashIcon } from '@/components/icons';
import { StarButton } from '@/components/StarButton';
import { Button } from '@/components/ui/button';
import { useDateStyle } from '@/features/preferences';
import { formatRecentDay } from '@/lib/dates';
import { pluralNoun } from '@/lib/plural';
import { formatSharpe } from '@/lib/results';
import { cn } from '@/lib/utils';

import { formatShape, formatSize } from './format';
import { FrameworkTile } from './FrameworkMark';
import { API_FRAMEWORKS } from './frameworks';

const HINT = 'text-xs/[1.5] text-muted-foreground';
const ACTION = cn(BUTTON_SIZES.sm, GHOST_BUTTON, 'font-medium');

type Props = {
  model: Model;
  onStar: (model: Model) => void;
  onRename: (model: Model) => void;
  onDelete: (model: Model) => void;
};

// The best Sharpe of its backtests and how many used it, side by side under a line.
function Stats({ model }: { model: Model }) {
  return (
    <div className="mt-auto grid grid-cols-2 gap-2 border-t pt-2.5">
      <div className="flex flex-col">
        <b className="font-mono text-[15px]/[normal] font-semibold">{formatSharpe(model.best_sharpe)}</b>
        <span className={HINT}>best Sharpe</span>
      </div>
      <div className="flex flex-col">
        <b className="font-mono text-[15px]/[normal] font-semibold">{model.backtest_count}</b>
        <span className={HINT}>{pluralNoun(model.backtest_count, 'backtest')}</span>
      </div>
    </div>
  );
}

// Rename and Delete as small ghost buttons along the foot; Delete turns red on hover.
function Actions({ model, onRename, onDelete }: Omit<Props, 'onStar'>) {
  return (
    <div className="-mx-2 -mb-1.5 flex min-h-7 items-center gap-1">
      <Button
        type="button"
        variant="ghost"
        className={ACTION}
        aria-label={`Rename ${model.name}`}
        onClick={() => onRename(model)}
      >
        <PencilIcon className="size-3.5" />
        Rename
      </Button>
      <Button
        type="button"
        variant="ghost"
        className={cn(ACTION, 'hover:text-down')}
        aria-label={`Delete ${model.name}`}
        onClick={() => onDelete(model)}
      >
        <TrashIcon className="size-3.5" />
        Delete
      </Button>
    </div>
  );
}

// A model on the Models page (mockups/app, mdTile): a square card with the framework's mark and
// the star, the name, what it is, the shape it reads, its results, then Rename and Delete.
export function ModelTile({ model, onStar, onRename, onDelete }: Props) {
  const framework = API_FRAMEWORKS[model.framework];
  const shape = formatShape(model.input_shape, model.output_shape);
  const dateStyle = useDateStyle();
  return (
    <article className="flex aspect-square min-w-0 flex-col gap-2.5 rounded-lg border bg-card p-4 transition-[border-color,box-shadow] duration-150 hover:border-[color-mix(in_srgb,var(--accent)_35%,var(--rule))] hover:shadow-[0_4px_14px_var(--shadow)] motion-reduce:transition-none">
      <div className="flex items-start justify-between">
        <FrameworkTile framework={framework} size="lg" />
        <StarButton
          starred={model.starred}
          label={`Star model ${model.name}`}
          onToggle={() => onStar(model)}
          className="m-0 -mt-1 -mr-1.5 text-[21px]"
        />
      </div>
      <div className="flex min-w-0 flex-col gap-0.5">
        <b className="truncate font-semibold" title={model.name}>
          {model.name}
        </b>
        <span className={HINT}>
          {framework} · {formatSize(model.size_bytes)} · added {formatRecentDay(new Date(model.created_at), dateStyle)}
        </span>
      </div>
      <div className="font-mono text-xs/[normal] text-muted-foreground">
        {shape === null ? 'Shape not in the file' : `in ${shape}`}
      </div>
      <Stats model={model} />
      <Actions model={model} onRename={onRename} onDelete={onDelete} />
    </article>
  );
}

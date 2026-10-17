import { useState } from 'react';

import type { Model } from '@/api';

import { DeleteDialog } from './DeleteDialog';
import { ModelTile } from './ModelTile';
import { RenameDialog } from './RenameDialog';
import { useStarModel } from './useModels';

// The dialog a tile opened. It keeps its model while it fades out.
type Open = { kind: 'rename' | 'delete'; model: Model; open: boolean };

// The tiles in the API's order (oldest first), 208 px at least, as many as fit in a row, and the
// Rename and Delete dialogs they open. No models, no tiles: the title row says how many.
export function ModelsGrid({ models }: { models: Model[] }) {
  const [dialog, setDialog] = useState<Open | null>(null);
  const star = useStarModel();
  const onOpenChange = (open: boolean) => setDialog((current) => current && { ...current, open });
  const dialogOf = (kind: Open['kind']) => ({
    model: dialog?.kind === kind ? dialog.model : null,
    open: dialog?.kind === kind && dialog.open,
    onOpenChange,
  });

  return (
    <>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(208px,1fr))] gap-4">
        {models.map((model) => (
          <ModelTile
            key={model.id}
            model={model}
            onStar={(item) => star.mutate(item)}
            onRename={(item) => setDialog({ kind: 'rename', model: item, open: true })}
            onDelete={(item) => setDialog({ kind: 'delete', model: item, open: true })}
          />
        ))}
      </div>
      <RenameDialog {...dialogOf('rename')} />
      <DeleteDialog {...dialogOf('delete')} />
    </>
  );
}

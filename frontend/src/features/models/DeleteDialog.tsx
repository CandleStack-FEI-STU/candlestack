import type { Model } from '@/api';
import { CancelButton, DangerButton } from '@/components/DialogButtons';
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { plural } from '@/lib/plural';

import { formatSize } from './format';
import { isGone, useDeleteModel } from './useModels';

// What happens to the backtests that used the model: they stay.
function backtestsNote(count: number): string {
  if (count === 0) return '';
  if (count === 1) return ' The backtest that used it stays, with its results.';
  return ` The ${plural(count, 'backtest')} that used it stay, with their results.`;
}

function deleteText(model: Model): string {
  return `The file goes from your models and frees ${formatSize(model.size_bytes)}.${backtestsNote(model.backtest_count)} This cannot be undone.`;
}

type FormProps = { model: Model; onDone: () => void };

function DeleteForm({ model, onDone }: FormProps) {
  const remove = useDeleteModel();
  return (
    <>
      <DialogBody>
        <DialogDescription className="text-sm/[1.5] text-foreground">{deleteText(model)}</DialogDescription>
        {remove.isError && (
          <p role="alert" className="text-[12.5px] text-down">
            {remove.error.message}
          </p>
        )}
      </DialogBody>
      <DialogFooter>
        <CancelButton />
        <DangerButton
          disabled={remove.isPending}
          onClick={() => remove.mutate(model, { onSuccess: onDone, onError: (error) => isGone(error) && onDone() })}
        >
          Delete
        </DangerButton>
      </DialogFooter>
    </>
  );
}

type Props = { model: Model | null; open: boolean; onOpenChange: (open: boolean) => void };

// Delete {name}? (mockups/app, MODALS.del). The model stays while the dialog fades out.
export function DeleteDialog({ model, open, onOpenChange }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="min-w-0 break-words">{model ? `Delete ${model.name}?` : 'Delete model?'}</DialogTitle>
        </DialogHeader>
        {model && <DeleteForm key={model.id} model={model} onDone={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  );
}

import { LoaderCircle, XIcon } from 'lucide-react';
import type { ReactNode } from 'react';

import type { Model } from '@/api';
import { CheckIcon, ClockIcon } from '@/components/icons';
import { cn } from '@/lib/utils';

import { formatParameters, formatShape, formatUsage } from './format';
import type { UploadFailure } from './useUpload';

// A hint under a line of the dialog (.mdl .h).
export const DIALOG_HINT = 'block text-[12.5px] text-muted-foreground';

const MUTED = 'bg-surface-2 text-muted-foreground';
const TONES = {
  ok: { icon: <CheckIcon />, tile: 'bg-[color-mix(in_srgb,var(--up)_15%,var(--bg))] text-up', state: 'Passed' },
  bad: { icon: <XIcon />, tile: 'bg-[color-mix(in_srgb,var(--down)_15%,var(--bg))] text-down', state: 'Failed' },
  // While the upload runs: the same row, a small spinner on a muted circle.
  pending: {
    icon: <LoaderCircle className="animate-spin motion-reduce:animate-none" />,
    tile: MUTED,
    state: 'Checking',
  },
  soon: { icon: <ClockIcon />, tile: MUTED, state: 'Not yet' },
};

type RowProps = { tone: keyof typeof TONES; title: string; hint?: string | undefined };

// A check (.ck-r): its state in a 22 px circle, the title, a hint under it.
function CheckRow({ tone, title, hint }: RowProps) {
  const { icon, tile, state } = TONES[tone];
  return (
    <li className="flex items-start gap-2.5">
      <span className={cn('grid size-[22px] flex-none place-items-center rounded-full [&_svg]:size-[13px]', tile)}>
        {icon}
      </span>
      <span className="min-w-0">
        <span className="sr-only">{state}: </span>
        <b className="font-medium">{title}</b>
        {hint && <span className={DIALOG_HINT}>{hint}</span>}
      </span>
    </li>
  );
}

function Checks({ children }: { children: ReactNode }) {
  return (
    <ul aria-live="polite" className="flex flex-col gap-2.5">
      {children}
    </ul>
  );
}

const OPENS = 'Opens as a Keras model, no custom code inside';
const WEIGHTS = 'Trained weights inside';

export function ComingSoonCheck() {
  return (
    <Checks>
      <CheckRow
        tone="soon"
        title="Support for this format is coming soon"
        hint="For now CandleStack takes Keras models (.keras)."
      />
    </Checks>
  );
}

export function PendingChecks() {
  return (
    <Checks>
      <CheckRow tone="pending" title={OPENS} />
      <CheckRow tone="pending" title={WEIGHTS} />
    </Checks>
  );
}

// Both checks passed, and the model as the app now has it.
export function PassedChecks({ model }: { model: Model }) {
  const parameters = `${formatParameters(model.parameters)} parameters`;
  const shape = formatShape(model.input_shape, model.output_shape, true);
  return (
    <>
      <Checks>
        <CheckRow tone="ok" title={OPENS} />
        <CheckRow tone="ok" title={WEIGHTS} hint={parameters} />
      </Checks>
      <div className="rounded-lg border border-[color-mix(in_srgb,var(--up)_35%,var(--rule))] bg-[color-mix(in_srgb,var(--up)_10%,var(--bg))] px-3.5 py-3">
        <b className="font-bold break-words">{model.name} is ready</b>
        <span className={DIALOG_HINT}>
          Keras · {parameters}
          {shape !== null && ` · in ${shape}`}
        </span>
      </div>
    </>
  );
}

function failedRow(failure: UploadFailure): RowProps {
  switch (failure.kind) {
    case 'opens':
      return { tone: 'bad', title: 'Does not open as a safe Keras model', hint: failure.detail };
    case 'weights':
      return {
        tone: 'bad',
        title: 'No trained weights in the file',
        hint: 'It holds the layers only. Save the model after training and upload that file.',
      };
    case 'large':
      return { tone: 'bad', title: 'Larger than 50 MB', hint: failure.detail };
    case 'storage':
      return {
        tone: 'bad',
        title: 'Not enough storage',
        hint: `${formatUsage(failure.used, failure.quota)} used. Delete a model to free space.`,
      };
    case 'other':
      return { tone: 'bad', title: 'Upload failed', hint: failure.detail };
  }
}

// The check that failed; a file without weights passed the first one.
export function FailedChecks({ failure }: { failure: UploadFailure }) {
  return (
    <Checks>
      {failure.kind === 'weights' && <CheckRow tone="ok" title={OPENS} />}
      <CheckRow {...failedRow(failure)} />
    </Checks>
  );
}

import { useNavigate, useRouterState } from '@tanstack/react-router';
import { useRef, useState, type ReactNode } from 'react';

import { CancelButton, OutlineButton, PrimaryButton } from '@/components/DialogButtons';
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DIALOG_HINT,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';

import { DropZone } from './DropZone';
import { formatSize } from './format';
import { FrameworkTile } from './FrameworkMark';
import { ACCEPTED_EXTENSIONS, frameworkOfFile } from './frameworks';
import { ComingSoonCheck, FailedChecks, PassedChecks, PendingChecks } from './UploadChecks';
import { useUpload, type UploadState } from './useUpload';

// The chosen file (.up-file): its framework's mark, its name, the framework and its size. A file
// of no known framework shows its name only.
function FileRow({ file }: { file: File }) {
  const framework = frameworkOfFile(file.name);
  return (
    <div className="flex items-center gap-2.5 rounded-lg border px-3 py-2.5">
      {framework && <FrameworkTile framework={framework} />}
      <span className="min-w-0">
        <b className="font-bold break-words">{file.name}</b>
        {framework && (
          <span className={cn('block', DIALOG_HINT)}>
            {framework} · {formatSize(file.size)}
          </span>
        )}
      </span>
    </div>
  );
}

function Result({ state }: { state: Exclude<UploadState, { step: 'pick' }> }) {
  switch (state.step) {
    case 'soon':
      return <ComingSoonCheck />;
    case 'checking':
      return <PendingChecks />;
    case 'ready':
      return <PassedChecks model={state.model} />;
    case 'failed':
      return <FailedChecks failure={state.failure} />;
  }
}

// The file and its checks, in a live region mounted in every step, so screen readers hear each
// result, the ready model too. Empty, it has no height and its negative margin cancels the
// body's gap (14 px), so it stays in the accessibility tree without moving the layout.
function Results({ state }: { state: UploadState }) {
  return (
    <div aria-live="polite" className="flex flex-col gap-3.5 empty:-mt-3.5">
      {state.step !== 'pick' && (
        <>
          <FileRow file={state.file} />
          <Result state={state} />
        </>
      )}
    </div>
  );
}

type FooterProps = { state: UploadState; onAgain: () => void; onDone: () => void; onBacktest: () => void };

// No buttons over the drop zone; Cancel while the checks run; Done or Backtest with it once the
// model is kept; otherwise Cancel or Choose another file.
function Footer({ state, onAgain, onDone, onBacktest }: FooterProps) {
  if (state.step === 'pick') return null;
  if (state.step === 'checking') {
    return (
      <DialogFooter>
        <CancelButton />
      </DialogFooter>
    );
  }
  if (state.step === 'ready') {
    return (
      <DialogFooter>
        <OutlineButton onClick={onDone}>Done</OutlineButton>
        <PrimaryButton onClick={onBacktest}>Backtest with it</PrimaryButton>
      </DialogFooter>
    );
  }
  return (
    <DialogFooter>
      <CancelButton />
      <PrimaryButton onClick={onAgain}>Choose another file</PrimaryButton>
    </DialogFooter>
  );
}

type FlowProps = { onDone: () => void; onBacktest: () => void };

// The dialog's content: the drop zone, then the file and its checks. It mounts with the dialog
// and unmounts with it, which aborts an upload still running.
function UploadFlow({ onDone, onBacktest }: FlowProps) {
  const { state, choose, reset } = useUpload();
  const input = useRef<HTMLInputElement>(null);
  const pick = () => input.current?.click();

  return (
    <>
      <DialogBody>
        <input
          ref={input}
          type="file"
          accept={ACCEPTED_EXTENSIONS}
          hidden
          aria-label="Model file"
          onChange={(event) => {
            const file = event.target.files?.[0];
            // Cleared, so choosing the same file again is a change too.
            event.target.value = '';
            if (file) choose(file);
          }}
        />
        {state.step === 'pick' && <DropZone onPick={pick} onDrop={choose} />}
        <Results state={state} />
      </DialogBody>
      <Footer
        state={state}
        onAgain={() => {
          reset();
          pick();
        }}
        onDone={onDone}
        onBacktest={onBacktest}
      />
    </>
  );
}

type Props = {
  // The button that opens the dialog.
  children: ReactNode;
  // Backtest with it: what opens once the model is kept (the New backtest dialog for now).
  onBacktest: () => void;
};

// Upload model (mockups/app, MODALS.upload): a Keras file goes to the API, which checks that it
// opens as a safe Keras model and holds trained weights before it keeps it. Done closes it and
// shows the Models page, where the new model has joined the tiles.
export function UploadDialog({ children, onBacktest }: Props) {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (router) => router.location.pathname });
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent aria-describedby={undefined}>
        <DialogHeader>
          <DialogTitle>Upload model</DialogTitle>
        </DialogHeader>
        <UploadFlow
          onDone={() => {
            setOpen(false);
            if (pathname !== '/models') void navigate({ to: '/models' });
          }}
          onBacktest={() => {
            setOpen(false);
            onBacktest();
          }}
        />
      </DialogContent>
    </Dialog>
  );
}

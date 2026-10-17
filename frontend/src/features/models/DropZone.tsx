import { useState, type DragEvent } from 'react';

import { DIALOG_HINT } from '@/components/ui/dialog';

import { FrameworkMini } from './FrameworkMark';
import { FRAMEWORKS } from './frameworks';
import { UploadIconTile } from './UploadCard';

type Props = { onPick: () => void; onDrop: (file: File) => void };

// Where a file goes (mockups/app, .up-drop): a click opens the file picker, a file dropped on it
// is taken; the dashed border turns to the accent while one is dragged over it. Its children take
// no pointer events, so moving over them is not leaving the zone.
export function DropZone({ onPick, onDrop }: Props) {
  const [dragging, setDragging] = useState(false);

  const over = (event: DragEvent) => {
    event.preventDefault();
    setDragging(true);
  };
  const drop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) onDrop(file);
  };

  return (
    <button
      type="button"
      onClick={onPick}
      onDragEnter={over}
      onDragOver={over}
      onDragLeave={() => setDragging(false)}
      onDrop={drop}
      data-dragging={dragging || undefined}
      className="flex w-full cursor-pointer flex-col items-center gap-2 rounded-[10px] border-[1.5px] border-dashed border-[color-mix(in_srgb,var(--accent)_35%,var(--rule))] bg-muted px-4 py-[30px] text-center transition-[border-color] duration-150 outline-none hover:border-primary focus-visible:ring-[3px] focus-visible:ring-ring/50 data-dragging:border-primary motion-reduce:transition-none [&>*]:pointer-events-none"
    >
      <UploadIconTile />
      <b className="font-bold">Drop a trained model here</b>
      <span className={DIALOG_HINT}>or click to choose a file. Up to 50 MB.</span>
      <span className="mt-1.5 flex flex-wrap items-center justify-center gap-3">
        {FRAMEWORKS.map((framework) => (
          <span key={framework} className="inline-flex items-center gap-[5px] text-xs/[1.5] text-muted-foreground">
            <FrameworkMini framework={framework} named={false} />
            {framework}
          </span>
        ))}
      </span>
    </button>
  );
}

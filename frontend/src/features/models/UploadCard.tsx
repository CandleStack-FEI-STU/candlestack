import type { ComponentProps } from 'react';

import { UploadIcon } from '@/components/icons';
import { cn } from '@/lib/utils';

import { FrameworkMini } from './FrameworkMark';
import { FRAMEWORKS } from './frameworks';

// The upload icon on a 36 px tile (.qa-i), on the card and in the drop zone.
export function UploadIconTile() {
  return (
    <span className="grid size-9 flex-none place-items-center rounded-[9px] bg-surface-2 text-foreground">
      <UploadIcon className="size-[18px]" />
    </span>
  );
}

// The quick action that opens the upload dialog (mockups/app, .qa-c): the icon, "Upload model"
// and the marks of the five frameworks. It rises 1 px with a shadow on hover. A button, so the
// dialog's trigger can pass its props on.
export function UploadCard({ className, ...props }: ComponentProps<'button'>) {
  return (
    <button
      type="button"
      className={cn(
        'flex min-w-0 cursor-pointer items-center gap-3 rounded-[10px] border bg-card px-4 py-3.5 text-left transition-[background-color,border-color,box-shadow,translate] duration-150 outline-none hover:-translate-y-px hover:border-[color-mix(in_srgb,var(--accent)_45%,var(--rule))] hover:bg-muted hover:shadow-[0_4px_14px_var(--shadow)] focus-visible:ring-[3px] focus-visible:ring-ring/50 motion-reduce:transition-none',
        className,
      )}
      {...props}
    >
      <UploadIconTile />
      <span className="flex min-w-0 flex-col gap-[3px]">
        <b className="font-semibold">Upload model</b>
        <span className="flex flex-wrap items-center gap-[7px]">
          {FRAMEWORKS.map((framework) => (
            <FrameworkMini key={framework} framework={framework} />
          ))}
        </span>
      </span>
    </button>
  );
}

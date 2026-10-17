import type { ComponentProps } from 'react';

import { UploadIcon } from '@/components/icons';
import { QuickAction, QuickActionTile } from '@/components/QuickAction';

import { FrameworkMini } from './FrameworkMark';
import { FRAMEWORKS } from './frameworks';

// The upload icon on a 36 px tile (.qa-i), on the card and in the drop zone.
export function UploadIconTile() {
  return <QuickActionTile icon={UploadIcon} />;
}

// The quick action that opens the upload dialog (mockups/app, .qa-c): the icon, "Upload model"
// and the marks of the five frameworks.
export function UploadCard(props: ComponentProps<'button'>) {
  return (
    <QuickAction
      icon={UploadIcon}
      title="Upload model"
      line={
        <span className="flex flex-wrap items-center gap-[7px]">
          {FRAMEWORKS.map((framework) => (
            <FrameworkMini key={framework} framework={framework} />
          ))}
        </span>
      }
      {...props}
    />
  );
}

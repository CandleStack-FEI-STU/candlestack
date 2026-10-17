import type { ComponentProps } from 'react';

import { ACCENT_BUTTON, BUTTON_SIZES, DANGER_ACCENT_BUTTON, OUTLINE_BUTTON } from '@/components/buttonStyles';
import { Button } from '@/components/ui/button';
import { DialogClose } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';

// The footer buttons of the app's dialogs (mockups/app, .mdl-f): .btn, .btn.pri and
// .btn.danger.pri, on shadcn's outline and default variants.

type Props = Omit<ComponentProps<typeof Button>, 'variant' | 'size'>;

export function OutlineButton({ className, ...props }: Props) {
  return (
    <Button
      type="button"
      variant="outline"
      className={cn(BUTTON_SIZES.default, OUTLINE_BUTTON, className)}
      {...props}
    />
  );
}

export function PrimaryButton({ className, ...props }: Props) {
  return <Button type="button" className={cn(BUTTON_SIZES.default, ACCENT_BUTTON, className)} {...props} />;
}

export function DangerButton({ className, ...props }: Props) {
  return <Button type="button" className={cn(BUTTON_SIZES.default, DANGER_ACCENT_BUTTON, className)} {...props} />;
}

// Cancel closes the dialog and changes nothing.
export function CancelButton() {
  return (
    <DialogClose asChild>
      <OutlineButton>Cancel</OutlineButton>
    </DialogClose>
  );
}

import * as React from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { XIcon } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

// shadcn/ui's Dialog with the app design's modal (mockups/app, modalShell): 560 px wide and at
// most the screen high less 16 px around it, a title row with the close button, a body that
// scrolls, and the buttons in a footer under a line. It fades and scales in from 10 px lower; the
// backdrop fades in.

function Dialog({ ...props }: React.ComponentProps<typeof DialogPrimitive.Root>) {
  return <DialogPrimitive.Root data-slot="dialog" {...props} />;
}

function DialogTrigger({ ...props }: React.ComponentProps<typeof DialogPrimitive.Trigger>) {
  return <DialogPrimitive.Trigger data-slot="dialog-trigger" {...props} />;
}

function DialogOverlay({ className, ...props }: React.ComponentProps<typeof DialogPrimitive.Overlay>) {
  return (
    <DialogPrimitive.Overlay
      data-slot="dialog-overlay"
      className={cn(
        'fixed inset-0 z-50 bg-black/45 duration-160 ease-out data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0 motion-reduce:animate-none',
        className,
      )}
      {...props}
    />
  );
}

// Tells `onMount` the element with the focus as the dialog's content mounts: a layout effect, so
// before anything inside (the Rename dialog's field, say) takes the focus.
function NoteOpener({ onMount }: { onMount: (element: HTMLElement) => void }) {
  React.useLayoutEffect(() => {
    if (document.activeElement instanceof HTMLElement) onMount(document.activeElement);
  }, [onMount]);
  return null;
}

// Radix gives the focus back to the dialog's DialogTrigger on closing. Most dialogs of the app
// are opened by a button of their own (a row of a list, a quick action) without one, and the
// focus would fall to the page: it goes back to the element that had it when the dialog opened,
// while that is still on the page. Only the first element noted per opening counts, as React's
// strict mode mounts the content twice.
function useFocusReturn(onCloseAutoFocus?: (event: Event) => void) {
  const opener = React.useRef<HTMLElement | null>(null);
  const noteOpener = React.useCallback((element: HTMLElement) => {
    opener.current ??= element;
  }, []);
  const returnFocus = (event: Event) => {
    onCloseAutoFocus?.(event);
    const element = opener.current;
    opener.current = null;
    if (event.defaultPrevented || !element?.isConnected) return;
    event.preventDefault();
    element.focus();
  };
  return { noteOpener, returnFocus };
}

function DialogContent({
  className,
  children,
  onCloseAutoFocus,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Content>) {
  const { noteOpener, returnFocus } = useFocusReturn(onCloseAutoFocus);
  return (
    <DialogPrimitive.Portal data-slot="dialog-portal">
      <DialogOverlay />
      <DialogPrimitive.Content
        data-slot="dialog-content"
        onCloseAutoFocus={returnFocus}
        className={cn(
          'fixed top-1/2 left-1/2 z-50 flex max-h-[calc(100vh-32px)] w-[min(560px,calc(100%-32px))] -translate-1/2 flex-col rounded-xl border bg-background text-sm/[1.5] shadow-[0_20px_50px_var(--shadow)] outline-none supports-[height:100dvh]:max-h-[calc(100dvh-32px)]',
          'duration-220 ease-[cubic-bezier(0.2,0.8,0.2,1)] data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-97 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-97 data-[state=open]:slide-in-from-bottom-[10px] motion-reduce:animate-none',
          className,
        )}
        {...props}
      >
        <NoteOpener onMount={noteOpener} />
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

// The title row: the title, and the close button at the right.
function DialogHeader({ className, children, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="dialog-header"
      className={cn('flex items-center justify-between gap-3 pt-3.5 pr-4 pb-2.5 pl-5', className)}
      {...props}
    >
      {children}
      <DialogPrimitive.Close asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Close"
          className="size-[34px] dark:hover:bg-accent"
        >
          <XIcon />
        </Button>
      </DialogPrimitive.Close>
    </div>
  );
}

function DialogTitle({ className, ...props }: React.ComponentProps<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title
      data-slot="dialog-title"
      className={cn('text-[17px] leading-normal font-semibold', className)}
      {...props}
    />
  );
}

function DialogBody({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="dialog-body"
      className={cn('flex min-h-0 flex-col gap-3.5 overflow-auto px-5 pt-1 pb-[18px]', className)}
      {...props}
    />
  );
}

// The buttons under a line, at the right: Cancel, then what the dialog is for.
function DialogFooter({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="dialog-footer"
      className={cn('flex items-center justify-end gap-2 border-t px-5 py-3', className)}
      {...props}
    />
  );
}

function DialogClose({ ...props }: React.ComponentProps<typeof DialogPrimitive.Close>) {
  return <DialogPrimitive.Close data-slot="dialog-close" {...props} />;
}

// A line of the dialog in its hint style (.mdl .h): the description and the hints under a line.
const DIALOG_HINT = 'text-[12.5px] text-muted-foreground';

function DialogDescription({ className, ...props }: React.ComponentProps<typeof DialogPrimitive.Description>) {
  return (
    <DialogPrimitive.Description data-slot="dialog-description" className={cn(DIALOG_HINT, className)} {...props} />
  );
}

export {
  DIALOG_HINT,
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
};

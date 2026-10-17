import * as React from 'react';
import * as SelectPrimitive from '@radix-ui/react-select';
import { Check, ChevronDown } from 'lucide-react';

import { DROPDOWN_CHEVRON, DROPDOWN_TRIGGER } from '@/components/buttonStyles';
import { cn } from '@/lib/utils';

// shadcn/ui's Select in the look of the app design's dropdowns (mockups/app, .fp-t and .fp, as
// the Instruments filter): a 34 px bordered button with a chevron that turns while open, and a
// panel 6 px under it, left-aligned, that pops in from 4 px above. Radix gives it the listbox
// roles, the keyboard (arrows, Home, End, typing a name) and the focus back on the button.

function Select({ ...props }: React.ComponentProps<typeof SelectPrimitive.Root>) {
  return <SelectPrimitive.Root data-slot="select" {...props} />;
}

// The children show the choice (Radix's Value would only copy the entry's name); the chevron
// comes last. While open, the border takes on the accent.
function SelectTrigger({ className, children, ...props }: React.ComponentProps<typeof SelectPrimitive.Trigger>) {
  return (
    <SelectPrimitive.Trigger
      data-slot="select-trigger"
      className={cn(
        DROPDOWN_TRIGGER,
        'cursor-pointer data-[state=open]:border-[color-mix(in_srgb,var(--accent)_55%,var(--rule))]',
        className,
      )}
      {...props}
    >
      {children}
      <SelectPrimitive.Icon asChild>
        <ChevronDown className={DROPDOWN_CHEVRON} />
      </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
  );
}

function SelectContent({ className, children, ...props }: React.ComponentProps<typeof SelectPrimitive.Content>) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Content
        data-slot="select-content"
        position="popper"
        side="bottom"
        align="start"
        sideOffset={6}
        className={cn(
          'z-50 origin-(--radix-select-content-transform-origin) rounded-lg border bg-popover text-sm text-popover-foreground shadow-[0_10px_28px_var(--shadow)]',
          'duration-140 ease-out data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-98 data-[state=open]:slide-in-from-top-1 motion-reduce:animate-none',
          className,
        )}
        {...props}
      >
        <SelectPrimitive.Viewport className="flex flex-col gap-0.5 p-1.5">{children}</SelectPrimitive.Viewport>
      </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
  );
}

// An entry: what the children draw, then a check in the accent while it is the choice. `text` is
// its name for typing to jump to it.
function SelectItem({
  className,
  children,
  text,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Item> & { text: string }) {
  return (
    <SelectPrimitive.Item
      data-slot="select-item"
      textValue={text}
      className={cn(
        'flex cursor-pointer items-center gap-2 rounded-sm p-2 text-foreground transition-colors duration-150 outline-none select-none data-[highlighted]:bg-muted',
        className,
      )}
      {...props}
    >
      {children}
      <SelectPrimitive.ItemIndicator className="flex-none text-primary">
        <Check className="size-4" />
      </SelectPrimitive.ItemIndicator>
    </SelectPrimitive.Item>
  );
}

// The entry's name inside its children: Radix names the option by it.
const SelectItemText = SelectPrimitive.ItemText;

export { Select, SelectContent, SelectItem, SelectItemText, SelectTrigger };

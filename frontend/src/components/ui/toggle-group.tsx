import * as React from 'react';
import * as ToggleGroupPrimitive from '@radix-ui/react-toggle-group';

import { cn } from '@/lib/utils';

// shadcn/ui's ToggleGroup as the app design's segmented control (mockups/app, .seg): bordered
// 30 px buttons 4 px apart, muted; the chosen one in the accent with a 2 px accent rim. With one
// value it is a radio group: the arrows move between the options, and a click on the chosen one
// keeps it (onValueChange only hears a real choice).

type SingleProps<T extends string> = Omit<
  React.ComponentProps<typeof ToggleGroupPrimitive.Root>,
  'type' | 'value' | 'defaultValue' | 'onValueChange'
> & { value: T; onValueChange: (value: T) => void };

function ToggleGroup<T extends string>({ className, value, onValueChange, ...props }: SingleProps<T>) {
  return (
    <ToggleGroupPrimitive.Root
      data-slot="toggle-group"
      type="single"
      value={value}
      // An empty value is the chosen option clicked again: a choice stays made.
      onValueChange={(next) => next !== '' && onValueChange(next as T)}
      className={cn('inline-flex flex-wrap gap-1', className)}
      {...props}
    />
  );
}

function ToggleGroupItem({ className, ...props }: React.ComponentProps<typeof ToggleGroupPrimitive.Item>) {
  return (
    <ToggleGroupPrimitive.Item
      data-slot="toggle-group-item"
      className={cn(
        'h-[30px] min-w-10 cursor-pointer rounded-md border bg-background px-2.5 text-[13px] font-medium text-muted-foreground outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 data-[state=on]:border-primary data-[state=on]:text-primary data-[state=on]:shadow-[inset_0_0_0_1px_var(--accent)]',
        className,
      )}
      {...props}
    />
  );
}

export { ToggleGroup, ToggleGroupItem };

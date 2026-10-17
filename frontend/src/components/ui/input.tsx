import * as React from 'react';

import { cn } from '@/lib/utils';

// shadcn/ui's Input in the look of the app design's text field (mockups/app, .inp): 34 px high,
// a 6 px radius, 10 px either side, the text in the ink on the background, the focus ring in the
// accent and the border in the falling red while the value is invalid. The className sizes it and
// sets its font.
function Input({ className, type, ...props }: React.ComponentProps<'input'>) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        'h-[34px] w-full min-w-0 rounded-md border bg-background px-2.5 text-sm text-foreground outline-none placeholder:text-muted-foreground',
        'focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50',
        'aria-invalid:border-down',
        className,
      )}
      {...props}
    />
  );
}

export { Input };

import * as React from 'react';
import * as SliderPrimitive from '@radix-ui/react-slider';

import { cn } from '@/lib/utils';

// shadcn/ui's Slider with one thumb, in the app design's look (mockups/app, .st-sl): a 6 px track,
// the accent up to the value and the darker surface after it, a 16 px ring of the accent as the
// thumb, which grows a little on hover. The thumb carries the name and the value.
function Slider({
  className,
  'aria-label': label,
  'aria-valuetext': valueText,
  ...props
}: React.ComponentProps<typeof SliderPrimitive.Root> & { 'aria-label': string; 'aria-valuetext'?: string }) {
  return (
    <SliderPrimitive.Root
      data-slot="slider"
      className={cn('relative flex h-4 cursor-pointer touch-none items-center select-none', className)}
      {...props}
    >
      <SliderPrimitive.Track className="relative h-1.5 grow overflow-hidden rounded-[3px] bg-[color-mix(in_srgb,var(--ink)_9%,var(--bg))]">
        <SliderPrimitive.Range className="absolute h-full bg-primary" />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb
        aria-label={label}
        aria-valuetext={valueText}
        className="block size-4 rounded-full border-2 border-primary bg-background shadow-[0_1px_4px_var(--shadow)] transition-transform duration-150 outline-none hover:scale-115 focus-visible:ring-[3px] focus-visible:ring-ring/50"
      />
    </SliderPrimitive.Root>
  );
}

export { Slider };

import { Link } from '@tanstack/react-router';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

// The design's sizes: 34 px high, 42 px in the hero. No shadow and a solid background in both
// themes, as the buttons stand on the grid.
const SIZES = { default: 'h-[34px] px-3.5', lg: 'h-[42px] px-5 text-[15px]' };
const OUTLINE = 'shadow-none dark:bg-background dark:hover:bg-accent';

// No action on purpose: the backtest builder it will open is not built yet. The accent border is
// the design's: it makes the button 2 px wider and stays as a rim around the hover color.
export function TryBacktest() {
  return (
    <Button
      type="button"
      className={cn(
        SIZES.lg,
        'border border-primary shadow-none hover:bg-[color-mix(in_srgb,var(--accent)_86%,var(--ink))]',
      )}
    >
      Try Backtest
    </Button>
  );
}

type BrowseProps = { size?: keyof typeof SIZES; className?: string };

export function BrowseInstruments({ size = 'default', className }: BrowseProps) {
  return (
    <Button asChild variant="outline" className={cn(SIZES[size], OUTLINE, className)}>
      <Link to="/instruments">Browse instruments</Link>
    </Button>
  );
}

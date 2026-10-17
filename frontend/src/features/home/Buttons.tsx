import { Link } from '@tanstack/react-router';

import { ACCENT_BUTTON, BUTTON_SIZES, OUTLINE_BUTTON } from '@/components/buttonStyles';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

// To the sign-in page, like the header's Try Backtest: the first sign-in creates the account.
export function TryBacktest() {
  return (
    <Button asChild className={cn(BUTTON_SIZES.lg, ACCENT_BUTTON)}>
      <Link to="/signin">Try Backtest</Link>
    </Button>
  );
}

type BrowseProps = { size?: keyof typeof BUTTON_SIZES; className?: string };

export function BrowseInstruments({ size = 'default', className }: BrowseProps) {
  return (
    <Button asChild variant="outline" className={cn(BUTTON_SIZES[size], OUTLINE_BUTTON, className)}>
      <Link to="/instruments">Browse instruments</Link>
    </Button>
  );
}

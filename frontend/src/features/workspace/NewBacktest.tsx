import { Plus } from 'lucide-react';
import type { ReactNode } from 'react';

import { ComingSoonDialog } from '@/components/ComingSoonDialog';
import { ACCENT_BUTTON, BUTTON_SIZES } from '@/components/buttonStyles';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

import { BuilderSketch } from './BuilderSketch';

type DialogProps = { children?: ReactNode; open?: boolean; onOpenChange?: (open: boolean) => void };

// The New backtest dialog. The builder is designed separately, so for now it is the Coming soon
// dialog. Opened by its button, or by the caller (Backtest with it, after an upload).
export function NewBacktestDialog({ children, open, onOpenChange }: DialogProps) {
  return (
    <ComingSoonDialog
      title="New backtest"
      lead="Pick the data, a representation, a model and a rule, then run it against buy and hold."
      sketch={<BuilderSketch />}
      open={open}
      onOpenChange={onOpenChange}
    >
      {children}
    </ComingSoonDialog>
  );
}

// The app header's New backtest. On a phone only its plus shows, in a 34 px square; the plus is
// still a child there from sm up, so the button's own padding for an icon is set back to the
// text's.
export function NewBacktest() {
  return (
    <NewBacktestDialog>
      <Button
        type="button"
        aria-label="New backtest"
        className={cn(
          BUTTON_SIZES.default,
          ACCENT_BUTTON,
          'has-[>svg]:px-3.5 max-sm:w-[34px] max-sm:px-0 max-sm:has-[>svg]:px-0',
        )}
      >
        <Plus className="sm:hidden" />
        <span className="max-sm:hidden">New backtest</span>
      </Button>
    </NewBacktestDialog>
  );
}

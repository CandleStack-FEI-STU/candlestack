import type { ReactNode } from 'react';

import { ComingSoonDialog } from '@/components/ComingSoonDialog';
import { RunsSketch } from '@/components/RunsSketch';

// Compare backtests (mockups/app, MODALS.compare), Coming soon over the home page's sketch of a
// table of runs. `children` is the button that opens it.
export function CompareDialog({ children }: { children: ReactNode }) {
  return (
    <ComingSoonDialog
      title="Compare backtests"
      lead="Change one layer, run again and see which combination holds up across market conditions."
      sketch={<RunsSketch />}
    >
      {children}
    </ComingSoonDialog>
  );
}

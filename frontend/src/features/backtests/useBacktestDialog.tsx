import { useState } from 'react';

import type { Backtest } from '@/api';

import { BacktestDialog } from './BacktestDialog';

// The Backtest dialog of a list and how its rows open it. The backtest stays while the dialog
// fades out.
export function useBacktestDialog() {
  const [shown, setShown] = useState<{ backtest: Backtest | null; open: boolean }>({ backtest: null, open: false });
  const dialog = (
    <BacktestDialog
      backtest={shown.backtest}
      open={shown.open}
      onOpenChange={(open) => setShown((current) => ({ ...current, open }))}
    />
  );
  return { dialog, openBacktest: (backtest: Backtest) => setShown({ backtest, open: true }) };
}

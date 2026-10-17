import type { Backtest } from '@/api';
import { Bar } from '@/components/ComingSoon';
import { ComingSoonDialog } from '@/components/ComingSoonDialog';
import { useDateStyle } from '@/features/preferences';
import { formatRecentTime } from '@/lib/dates';

import { instrumentList, representationName, symbolsOf } from './format';

// The result tiles of a backtest's page: a heading over a value, two of them tinted as returns.
const TILES: readonly (readonly [heading: number, value: number, tone?: 'up' | 'down'])[] = [
  [55, 70, 'up'],
  [45, 50],
  [60, 55, 'down'],
  [50, 45],
];
const EQUITY = 'M0 70 L40 62 L80 66 L120 52 L160 56 L200 40 L240 46 L280 30 L320 36 L360 22 L400 26';
const BUY_AND_HOLD = 'M0 70 L50 64 L100 60 L150 58 L200 50 L250 48 L300 40 L350 38 L400 32';

// The sketch of a backtest's own page under its Coming soon tag (mockups/app, runSoon): four
// result tiles over a faint equity line and the dashed buy and hold.
function BacktestSketch() {
  return (
    <div className="flex flex-col gap-3.5">
      <div className="grid grid-cols-4 gap-2.5">
        {TILES.map(([heading, value, tone], index) => (
          <div key={index} className="flex flex-col gap-2 rounded-lg border p-3">
            <Bar width={heading} faint />
            <Bar width={value} tone={tone} />
          </div>
        ))}
      </div>
      <svg viewBox="0 0 400 80" preserveAspectRatio="none" className="block h-[90px] w-full">
        <path
          d={BUY_AND_HOLD}
          vectorEffect="non-scaling-stroke"
          strokeDasharray="6 5"
          className="fill-none stroke-[color-mix(in_srgb,var(--ink)_14%,var(--bg))] stroke-2"
        />
        <path
          d={EQUITY}
          vectorEffect="non-scaling-stroke"
          strokeLinejoin="round"
          className="fill-none stroke-[color-mix(in_srgb,var(--accent)_35%,var(--bg))] stroke-3"
        />
      </svg>
    </div>
  );
}

type Props = { backtest: Backtest | null; open: boolean; onOpenChange: (open: boolean) => void };

// What a backtest opens while its page is not built (mockups/app, MODALS.run): "Backtest #12",
// what it ran on and with what, and when. The backtest stays while the dialog fades out.
export function BacktestDialog({ backtest, open, onOpenChange }: Props) {
  const dateStyle = useDateStyle();
  const lead = backtest
    ? [
        instrumentList(symbolsOf(backtest)),
        representationName(backtest.representation),
        backtest.model.name,
        formatRecentTime(new Date(backtest.created_at), dateStyle),
      ].join(' · ')
    : '';
  return (
    <ComingSoonDialog
      title={backtest ? `Backtest #${backtest.number}` : 'Backtest'}
      lead={lead}
      sketch={<BacktestSketch />}
      open={open}
      onOpenChange={onOpenChange}
    />
  );
}

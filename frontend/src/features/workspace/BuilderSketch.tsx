import { Fragment } from 'react';

import { Bar } from '@/components/ComingSoon';

// The five blocks of a backtest (market data, the three layers, the result), wired left to right;
// the last one's value is a return.
const BLOCKS: readonly (readonly [heading: number, value: number])[] = [
  [60, 75],
  [70, 55],
  [65, 80],
  [55, 60],
  [60, 50],
];
const PANE = [80, 65, 72];

// The sketch of the backtest builder under its Coming soon tag (mockups/app, newSoon): the
// pipeline of blocks over the settings pane of the chosen one.
export function BuilderSketch() {
  return (
    <div className="flex flex-col gap-3.5">
      <div className="flex items-center">
        {BLOCKS.map(([heading, value], index) => (
          <Fragment key={index}>
            {index > 0 && <span className="h-0.5 flex-[0_0_14px] bg-border" />}
            <div className="flex min-w-0 flex-1 flex-col gap-2 rounded-lg border px-2.5 py-3">
              <Bar width={heading} faint />
              <Bar width={value} tone={index === BLOCKS.length - 1 ? 'up' : undefined} />
            </div>
          </Fragment>
        ))}
      </div>
      <div className="flex flex-col gap-3 rounded-lg border p-3.5">
        <Bar width={35} faint />
        {PANE.map((width, index) => (
          <Bar key={index} width={width} />
        ))}
      </div>
    </div>
  );
}

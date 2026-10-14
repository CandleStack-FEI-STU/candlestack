import { Link } from '@tanstack/react-router';
import { memo } from 'react';

import { cn } from '@/lib/utils';

import { candlePaths, candlesLabel, dayLabel, type CandlePaths, type Spark } from './candlePaths';

type Props = {
  id: string;
  spark: Spark;
  count: number;
  width: number;
  height: number;
  hover?: boolean;
  className?: string;
};

// A slot per day over the candles: hovering a day shows a 1 px hairline and "Oct 9 · close
// 82,635.55" above it. The layer lies over the row's stretched link, so it is a link to the
// instrument too, hidden from the keyboard and screen readers (the symbol stays the row's one tab
// stop).
function DayHover({ id, days }: { id: string; days: CandlePaths['days'] }) {
  return (
    <Link to="/instrument/$id" params={{ id }} tabIndex={-1} aria-hidden className="absolute inset-0 z-10 flex">
      {days.map((day, index) => (
        // The slots never move: the index is their key.
        <span key={index} className="group/day relative flex-1">
          {day && (
            <>
              <span className="absolute -inset-y-0.5 left-1/2 hidden w-px bg-muted-foreground/60 group-hover/day:block" />
              <span className="pointer-events-none absolute bottom-[calc(100%+5px)] left-1/2 z-20 hidden -translate-x-1/2 rounded bg-foreground px-1.5 font-mono text-[11px] leading-4 whitespace-nowrap text-background group-hover/day:block">
                {dayLabel(day)}
              </span>
            </>
          )}
        </span>
      ))}
    </Link>
  );
}

// The last daily candles of a list row (#189): 10 in 112 × 32 px on wide screens, the last 7 in
// 44 × 24 on phones (without the hover); a dashed line without any candle. Up `--candle-up`, down
// `--candle-down`, as on the chart.
export const MiniCandles = memo(function MiniCandles({ id, spark, count, width, height, hover, className }: Props) {
  const paths = candlePaths(spark, count, width, height);
  return (
    <span className={cn('relative block', className)} style={{ width, height }}>
      <span className="sr-only">{paths ? candlesLabel(paths.days) : 'No chart yet'}</span>
      <svg viewBox={`0 0 ${width} ${height}`} aria-hidden className="block size-full">
        {paths ? (
          <>
            <path className="fill-candle-up" d={paths.up} />
            <path className="fill-candle-down" d={paths.down} />
          </>
        ) : (
          <path
            className="fill-none stroke-muted-foreground/45"
            strokeWidth={1.5}
            strokeDasharray="3 3"
            d={`M1 ${height / 2}H${width - 1}`}
          />
        )}
      </svg>
      {hover && paths && <DayHover id={id} days={paths.days} />}
    </span>
  );
});

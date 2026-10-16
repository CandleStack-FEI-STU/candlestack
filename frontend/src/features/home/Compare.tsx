import { Bar, ComingSoon } from '@/components/ComingSoon';

import { Section, SectionIntro } from './Section';

// The sketch of the comparison: a table of runs under its header, the fourth column their return.
const HEADER = [60, 50, 45, 55, 60];
const RUNS: { widths: number[]; tone: 'up' | 'down' }[] = [
  { widths: [70, 85, 60, 72, 70], tone: 'up' },
  { widths: [55, 75, 70, 58, 70], tone: 'up' },
  { widths: [65, 90, 50, 50, 70], tone: 'down' },
  { widths: [60, 70, 65, 40, 70], tone: 'up' },
];
const ROW =
  'grid grid-cols-[0.7fr_1.3fr_1fr_0.8fr_0.6fr] items-center gap-[18px] border-b pb-3.5 last:border-b-0 last:pb-0';

function RunsSketch() {
  return (
    <div className="flex flex-col gap-3.5">
      <div className={ROW}>
        {HEADER.map((width, column) => (
          <Bar key={column} width={width} faint />
        ))}
      </div>
      {RUNS.map((run, row) => (
        <div key={row} className={ROW}>
          {run.widths.map((width, column) => (
            <Bar key={column} width={width} tone={column === 3 ? run.tone : undefined} />
          ))}
        </div>
      ))}
    </div>
  );
}

// Comparing runs comes later; the section says what it will do.
export function Compare() {
  return (
    <Section id="compare" split>
      <div>
        <SectionIntro
          eyebrow="Compare"
          title="Every run gets the same metrics"
          text="Change one layer, run again and see which combination holds up across market conditions."
        />
      </div>
      <ComingSoon>
        <RunsSketch />
      </ComingSoon>
    </Section>
  );
}

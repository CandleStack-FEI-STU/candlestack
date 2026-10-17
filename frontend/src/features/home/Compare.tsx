import { ComingSoon } from '@/components/ComingSoon';
import { RunsSketch } from '@/components/RunsSketch';

import { Section, SectionIntro } from './Section';

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

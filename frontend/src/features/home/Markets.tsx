import type { ReactNode } from 'react';

import { BrowseInstruments } from './Buttons';
import { Section, SectionIntro } from './Section';

// Which markets the data covers, with a way to the instrument list; `children` (the most traded
// instruments) fill the right column.
export function Markets({ children }: { children: ReactNode }) {
  return (
    <Section id="markets" split>
      <div>
        <SectionIntro
          eyebrow="Instruments"
          title="US stocks and crypto pairs, candles from 1m to 1d"
          text="Every US exchange through Alpaca since 2016, Binance spot pairs since their listing."
        />
        <BrowseInstruments className="mt-4" />
      </div>
      <div>{children}</div>
    </Section>
  );
}

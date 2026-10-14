import { Bar, ComingSoon } from './ComingSoon';
import { Section, SectionIntro } from './Section';

// The sketch of the catalog: three experiment cards, each with a title, a line, an equity curve
// (in a 100 × 28 box) and its return.
const CARDS = [
  { title: 78, line: 55, curve: 'M0 22 L14 18 L28 20 L42 12 L56 14 L70 8 L84 10 L100 4' },
  { title: 64, line: 70, curve: 'M0 18 L14 20 L28 14 L42 16 L56 10 L70 12 L84 6 L100 8' },
  { title: 72, line: 48, curve: 'M0 20 L14 14 L28 16 L42 8 L56 12 L70 6 L84 9 L100 3' },
];

function CardsSketch() {
  return (
    <div className="grid grid-cols-3 gap-2.5">
      {CARDS.map((card) => (
        <div key={card.curve} className="flex flex-col gap-2 rounded-lg border p-3">
          <Bar width={card.title} />
          <Bar width={card.line} faint />
          {/* Stretched to the card's width; the stroke stays 2 px. */}
          <svg viewBox="0 0 100 28" preserveAspectRatio="none" className="my-1 block h-[34px] w-full">
            <path
              d={card.curve}
              className="fill-none stroke-2 [stroke:color-mix(in_srgb,var(--accent)_40%,var(--bg))] [vector-effect:non-scaling-stroke]"
            />
          </svg>
          <div className="flex justify-between gap-2">
            <Bar width={34} tone="up" />
            <Bar width={26} faint />
          </div>
        </div>
      ))}
    </div>
  );
}

// Published experiments come later; the section says what the catalog will hold.
export function Experiments() {
  return (
    <Section id="experiments" split>
      <div>
        <SectionIntro
          eyebrow="Public experiments"
          title="A catalog of published experiments"
          text="Runs their authors chose to publish, each with its instrument, representation, model and decision settings and the same metrics, so anyone can look one up and run it again."
        />
      </div>
      <ComingSoon>
        <CardsSketch />
      </ComingSoon>
    </Section>
  );
}

import { Compare, Experiments, Hero, Layers, Markets, TopInstruments } from '@/features/home';
import { usePageTitle } from '@/lib/usePageTitle';

// The public start page (design repository, mockups/home): what a backtest is made of, the most
// traded instruments, and what comes next. The column is the Layout's, with the design's 14 px text.
export function HomePage() {
  usePageTitle('');
  return (
    <div className="text-sm/[1.5]">
      <Hero />
      <Layers />
      <Markets>
        <TopInstruments />
      </Markets>
      <Compare />
      <Experiments />
    </div>
  );
}

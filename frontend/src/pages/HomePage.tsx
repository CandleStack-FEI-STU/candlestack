import { Compare, Experiments, Hero, Layers, Markets, TopInstruments } from '@/features/home';
import { usePageTitle } from '@/lib/usePageTitle';

// The public start page (design repository, mockups/home): what a backtest is made of, the most
// traded instruments, and what comes next. The design's column is 1152 px with 14 px text, 28 px
// above it and 40 px below; the Layout's main has 32 px on both, hence -mt-1 and pb-2.
export function HomePage() {
  usePageTitle('');
  return (
    <div className="mx-auto -mt-1 w-full max-w-[72rem] pb-2 text-sm/[1.5]">
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

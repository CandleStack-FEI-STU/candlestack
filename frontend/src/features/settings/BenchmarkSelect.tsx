import type { Benchmark } from '@/api';
import { Select, SelectContent, SelectItem, SelectItemText, SelectTrigger } from '@/components/ui/select';

// What each backtest is measured against: its own instruments bought and kept, or an index fund.
// The short name is the tag before each, B&H for buy and hold.
const BENCHMARKS: Record<Benchmark, { tag: string; name: string; about: string }> = {
  bh: { tag: 'B&H', name: 'Buy and hold', about: 'The same instruments, bought and kept' },
  SPY: { tag: 'SPY', name: 'SPDR S&P 500 ETF', about: 'The 500 largest US companies' },
  QQQ: { tag: 'QQQ', name: 'Invesco QQQ', about: 'The Nasdaq 100' },
  DIA: { tag: 'DIA', name: 'SPDR Dow Jones ETF', about: 'The 30 Dow Jones companies' },
};

const ORDER: readonly Benchmark[] = ['bh', 'SPY', 'QQQ', 'DIA'];

// .st-bk: the short name in mono on the darker surface.
function Tag({ children }: { children: string }) {
  return (
    <span className="min-w-10 flex-none rounded-[5px] bg-[color-mix(in_srgb,var(--ink)_9%,var(--bg))] px-1.5 py-0.5 text-center font-mono text-[11.5px]/[normal] font-semibold text-foreground">
      {children}
    </span>
  );
}

// A 300 px button with the tag and the name of the choice; its 340 px list adds what each one is.
export function BenchmarkSelect({ value, onChange }: { value: Benchmark; onChange: (value: Benchmark) => void }) {
  const chosen = BENCHMARKS[value];
  return (
    <Select value={value} onValueChange={(next) => onChange(next as Benchmark)}>
      <SelectTrigger className="w-[300px] max-w-full" aria-label={`Benchmark: ${chosen.name}`}>
        <Tag>{chosen.tag}</Tag>
        <span className="min-w-0 flex-1 truncate text-foreground">{chosen.name}</span>
      </SelectTrigger>
      <SelectContent className="w-[340px]">
        {ORDER.map((key) => {
          const { tag, name, about } = BENCHMARKS[key];
          return (
            <SelectItem key={key} value={key} text={name}>
              <Tag>{tag}</Tag>
              <span className="flex min-w-0 flex-col">
                <SelectItemText>{name}</SelectItemText>
                <span className="text-[11.5px] text-muted-foreground">{about}</span>
              </span>
            </SelectItem>
          );
        })}
      </SelectContent>
    </Select>
  );
}

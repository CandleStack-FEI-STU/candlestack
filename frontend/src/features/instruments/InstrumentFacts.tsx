// What the list holds, in four chips under the title. The API has 14,567 instruments (October 2026).
const FACTS = [
  { value: '14,000+', label: 'instruments' },
  { value: '1m – 1d', label: 'candles' },
  { value: 'Jan 2016', label: 'first stock candles' },
  { value: 'Since listing', label: 'for crypto pairs' },
];

export function InstrumentFacts() {
  return (
    <ul className="mt-4 flex flex-wrap gap-2">
      {FACTS.map(({ value, label }) => (
        <li key={label} className="rounded-full border bg-background px-3 py-1 text-[13px] text-muted-foreground">
          <b className="mr-1 font-mono font-medium text-foreground">{value}</b> {label}
        </li>
      ))}
    </ul>
  );
}

import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';

// The controls of the cards of Settings (mockups/app, .st-c): the text field and the segments.

// .inp in a card: 34 px, the text in the app's sans, at most 260 px wide.
export const INPUT =
  'h-[34px] w-full max-w-[260px] min-w-0 rounded-md border bg-background px-2.5 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 aria-invalid:border-down';

// .seg in a card: one of a few options, each a segment with its text.
export function Choice<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: readonly (readonly [value: T, text: string])[];
  onChange: (value: T) => void;
}) {
  return (
    <ToggleGroup value={value} onValueChange={onChange} aria-label={label}>
      {options.map(([option, text]) => (
        <ToggleGroupItem key={option} value={option}>
          {text}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}

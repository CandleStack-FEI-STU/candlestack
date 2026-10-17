import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';

// The controls of the cards of Settings (mockups/app, .st-c): the segments.

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

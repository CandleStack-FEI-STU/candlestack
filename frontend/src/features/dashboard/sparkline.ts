// The paths of a small equity chart (mockups/app, spark): both lines on one scale, from the
// lowest to the highest value of either, 2 px from the top and the bottom; the points evenly
// spaced from the left edge to the right.
export function sparkPaths(
  strategy: readonly number[],
  benchmark: readonly number[],
  width: number,
  height: number,
): { strategy: string; benchmark: string } {
  const all = [...strategy, ...benchmark];
  const low = Math.min(...all);
  const high = Math.max(...all);
  const span = high - low;
  // A flat line sits in the middle.
  const y = (value: number) => (span === 0 ? height / 2 : 2 + ((high - value) / span) * (height - 4));
  const line = (values: readonly number[]) =>
    values
      .map((value, index) => {
        const x = values.length > 1 ? (index / (values.length - 1)) * width : 0;
        return `${index === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y(value).toFixed(1)}`;
      })
      .join('');
  return { strategy: line(strategy), benchmark: line(benchmark) };
}

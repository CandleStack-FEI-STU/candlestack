// The keys of a list of entries, as the Filters panels use them. `usable` holds the indexes of
// the entries that can get the focus, in order; `at` is the place in it of the entry that has it.

// The arrows, Home and End move through the list, stopping at the ends.
export function moveInList(usable: readonly number[], at: number, key: string): number | undefined {
  if (key === 'ArrowDown') return usable[Math.min(at + 1, usable.length - 1)];
  if (key === 'ArrowUp') return usable[Math.max(at - 1, 0)];
  if (key === 'Home') return usable[0];
  if (key === 'End') return usable.at(-1);
  return undefined;
}

// A letter goes to the next entry whose label starts with it, round the end.
export function typeAhead(
  labels: readonly string[],
  usable: readonly number[],
  at: number,
  key: string,
): number | undefined {
  if (key.length !== 1 || key.trim() === '') return undefined;
  const letter = key.toLowerCase();
  const after = [...usable.slice(at + 1), ...usable.slice(0, at + 1)];
  return after.find((index) => labels[index]?.toLowerCase().startsWith(letter));
}

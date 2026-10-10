// Which result gets the focus after a key press in the header search's list. `count` is the number of
// options; ArrowDown stops at the last one and ArrowUp at the first, like a native select.
export function moveActive(active: number, key: string, count: number): number {
  if (count === 0) return 0;
  if (key === 'ArrowDown') return Math.min(active + 1, count - 1);
  if (key === 'ArrowUp') return Math.max(active - 1, 0);
  if (key === 'Home') return 0;
  if (key === 'End') return count - 1;
  return active;
}

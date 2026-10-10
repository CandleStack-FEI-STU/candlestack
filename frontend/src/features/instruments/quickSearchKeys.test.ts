import { describe, expect, it } from 'vitest';

import { moveActive } from './quickSearchKeys';

describe('header search keys', () => {
  it('moves the highlight down and up, and stops at the ends', () => {
    expect(moveActive(0, 'ArrowDown', 3)).toBe(1);
    expect(moveActive(2, 'ArrowDown', 3)).toBe(2);
    expect(moveActive(1, 'ArrowUp', 3)).toBe(0);
    expect(moveActive(0, 'ArrowUp', 3)).toBe(0);
  });

  it('jumps to the first and the last option', () => {
    expect(moveActive(1, 'Home', 3)).toBe(0);
    expect(moveActive(0, 'End', 3)).toBe(2);
  });

  it('leaves the highlight alone for other keys and without options', () => {
    expect(moveActive(1, 'a', 3)).toBe(1);
    expect(moveActive(4, 'ArrowDown', 0)).toBe(0);
  });
});

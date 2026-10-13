import { describe, expect, it } from 'vitest';

import { clampedPage, lastPage } from './pagination';

describe('pages', () => {
  it('counts the pages, with page 1 even for nothing', () => {
    expect(lastPage(120, 50)).toBe(3);
    expect(lastPage(100, 50)).toBe(2);
    expect(lastPage(0, 50)).toBe(1);
  });

  it('brings a page past the end back to the last one', () => {
    expect(clampedPage(40, 120, 50)).toBe(3);
    expect(clampedPage(2, 0, 50)).toBe(1);
  });

  it('leaves a page that exists, and any page while the total is unknown', () => {
    expect(clampedPage(3, 120, 50)).toBeUndefined();
    expect(clampedPage(40, undefined, 50)).toBeUndefined();
  });
});

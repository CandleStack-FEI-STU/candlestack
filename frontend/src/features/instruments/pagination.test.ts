import { describe, expect, it } from 'vitest';

import { clampedPage, lastPage, listBodyState } from './pagination';

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

describe('listBodyState', () => {
  it('shows the rows there are', () => {
    expect(listBodyState(25, false, 1)).toBe('rows');
    expect(listBodyState(3, true, 2)).toBe('rows');
  });

  it('says "Loading" for an empty result that is not the answer yet', () => {
    // the previous query's result standing in, or a page being clamped
    expect(listBodyState(0, true, 1)).toBe('loading');
    expect(listBodyState(0, true, 40)).toBe('loading');
  });

  it('tells an empty search from a page past the end', () => {
    expect(listBodyState(0, false, 1)).toBe('empty');
    expect(listBodyState(0, false, 4)).toBe('past');
  });
});

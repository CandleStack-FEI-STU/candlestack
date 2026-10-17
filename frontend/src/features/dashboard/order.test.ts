import { describe, expect, it } from 'vitest';

import { model } from '@/test/api';

import { showsStarredModels, starredModels } from './order';

const STARRED = model({ starred: true });
const PLAIN = model({ id: 'mdl_a2b3c4d5e6' });

describe('starredModels', () => {
  it('keeps the starred models, the best Sharpe first, then the most used', () => {
    const a = model({ id: 'mdl_a', starred: true, best_sharpe: 0.5, backtest_count: 1 });
    const b = model({ id: 'mdl_b', starred: true, best_sharpe: 1.2 });
    const c = model({ id: 'mdl_c', starred: true, best_sharpe: null, backtest_count: 4 });
    const d = model({ id: 'mdl_d', starred: true, best_sharpe: null, backtest_count: 0 });
    expect(starredModels([d, PLAIN, a, c, b]).map((item) => item.id)).toEqual(['mdl_b', 'mdl_a', 'mdl_c', 'mdl_d']);
  });
});

describe('showsStarredModels', () => {
  it('waits for the models, and shows why when they could not load', () => {
    expect(showsStarredModels(undefined, false, true)).toBe(false);
    expect(showsStarredModels(undefined, true, true)).toBe(true);
    expect(showsStarredModels(undefined, true, false)).toBe(true);
  });

  it('always shows with backtests, and in a new account once a model is starred', () => {
    expect(showsStarredModels([], false, true)).toBe(true);
    expect(showsStarredModels([PLAIN], false, false)).toBe(false);
    expect(showsStarredModels([PLAIN, STARRED], false, false)).toBe(true);
  });
});

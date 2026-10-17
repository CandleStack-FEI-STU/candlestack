import type { Model } from '@/api';

// The starred models, the best Sharpe ratio of their backtests first (those without one last),
// then the most used (mockups/app, ddStarredModels).
export function starredModels(models: readonly Model[]): Model[] {
  return models
    .filter((model) => model.starred)
    .sort((a, b) => (b.best_sharpe ?? -Infinity) - (a.best_sharpe ?? -Infinity) || b.backtest_count - a.backtest_count);
}

// Whether Starred models shows: once the models have loaded, always in an account with backtests
// and in a new one when a model is starred; while they load, not at all; when they could not
// load, to say why.
export function showsStarredModels(models: readonly Model[] | undefined, failed: boolean, full: boolean): boolean {
  if (!models) return failed;
  return full || models.some((model) => model.starred);
}

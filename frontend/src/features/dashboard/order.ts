import type { Model } from '@/api';

// The starred models, the best Sharpe ratio of their backtests first (those without one last),
// then the most used (mockups/app, ddStarredModels).
export function starredModels(models: readonly Model[]): Model[] {
  return models
    .filter((model) => model.starred)
    .sort((a, b) => (b.best_sharpe ?? -Infinity) - (a.best_sharpe ?? -Infinity) || b.backtest_count - a.backtest_count);
}

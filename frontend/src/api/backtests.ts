import { keepPreviousData, queryOptions } from '@tanstack/react-query';

import { get, patch } from './client';
import type { components } from './schema';

// A backtest as the API sends it. Returns and rates are fractions (0.246 is 24.6 %); the results
// are null for a backtest that did not finish.
export type Backtest = components['schemas']['BacktestOut'];
export type BacktestsPage = components['schemas']['BacktestsPage'];
export type BacktestShow = components['schemas']['BacktestShow'];
export type BacktestSort = components['schemas']['BacktestSort'];
export type SortOrder = components['schemas']['SortOrder'];
export type Representation = components['schemas']['Representation'];
export type Dashboard = components['schemas']['DashboardOut'];
// The results Best backtests ranks by.
export type BestMetric = keyof Dashboard['best'];

// What the Backtests page asks for; a value left out is the API's default (all, newest first,
// page 1).
export type BacktestsParams = {
  q?: string | undefined;
  show?: Exclude<BacktestShow, 'all'> | undefined;
  model?: string | undefined;
  sort?: Exclude<BacktestSort, 'default'> | undefined;
  order?: SortOrder | undefined;
  page?: number | undefined;
};

// GET /api/v1/backtests: a page of 10, with the counts and the models the filters offer.
function listBacktests(params: BacktestsParams, signal?: AbortSignal): Promise<BacktestsPage> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') query.set(key, String(value));
  }
  const text = query.toString();
  return get<BacktestsPage>(text === '' ? '/v1/backtests' : `/v1/backtests?${text}`, signal);
}

// Under ['account', 'backtests', ...] so signing out forgets them and a star can update every
// page at once. While the next page, search or order loads, the previous one stays on screen.
export function backtestsQueryOptions(params: BacktestsParams) {
  return queryOptions({
    queryKey: ['account', 'backtests', params],
    queryFn: ({ signal }) => listBacktests(params, signal),
    placeholderData: keepPreviousData,
  });
}

// GET /api/v1/dashboard: the counts, the newest, the best and the starred backtests at once. The
// sidebar's count comes from it too.
export function dashboardQueryOptions() {
  return queryOptions({
    queryKey: ['account', 'dashboard'],
    queryFn: ({ signal }) => get<Dashboard>('/v1/dashboard', signal),
  });
}

// PATCH /api/v1/backtests/{id}: stars or unstars the backtest.
export function updateBacktest(id: string, update: components['schemas']['BacktestUpdate']): Promise<Backtest> {
  return patch<Backtest>(`/v1/backtests/${encodeURIComponent(id)}`, update);
}

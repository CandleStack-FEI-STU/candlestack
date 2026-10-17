import { QueryClient } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { backtest, backtestsAnswer, dashboardAnswer, problem, stubApi } from '@/test/api';

import { backtestsQueryOptions, dashboardQueryOptions, updateBacktest } from './backtests';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('backtestsQueryOptions', () => {
  it('asks for the plain list without a query, under the account', async () => {
    const fetch = stubApi(backtestsAnswer({ backtests: [backtest()] }));
    const options = backtestsQueryOptions({});
    expect(options.queryKey).toEqual(['account', 'backtests', {}]);
    const data = await new QueryClient().fetchQuery(options);
    expect(data.backtests).toEqual([backtest()]);
    expect(fetch.mock.calls[0]?.[0]).toBe('/api/v1/backtests');
  });

  it('sends the search, the filters, the order and the page that are set', async () => {
    const query = '?q=aapl+%2312&show=starred&model=blesk-novol-8.keras&sort=sharpe&order=asc&page=2';
    const fetch = stubApi(backtestsAnswer({}, query));
    const params = {
      q: 'aapl #12',
      show: 'starred',
      model: 'blesk-novol-8.keras',
      sort: 'sharpe',
      order: 'asc',
      page: 2,
    } as const;
    await new QueryClient().fetchQuery(backtestsQueryOptions(params));
    expect(fetch.mock.calls[0]?.[0]).toBe(`/api/v1/backtests${query}`);
  });

  it('leaves out what is not set', async () => {
    const fetch = stubApi(backtestsAnswer({}, '?show=failed'));
    await new QueryClient().fetchQuery(backtestsQueryOptions({ q: '', show: 'failed', page: undefined }));
    expect(fetch.mock.calls[0]?.[0]).toBe('/api/v1/backtests?show=failed');
  });
});

describe('dashboardQueryOptions', () => {
  it('reads the dashboard under the account', async () => {
    stubApi(dashboardAnswer({ last: [backtest()] }));
    const options = dashboardQueryOptions();
    expect(options.queryKey).toEqual(['account', 'dashboard']);
    const data = await new QueryClient().fetchQuery(options);
    expect(data.last).toEqual([backtest()]);
  });
});

describe('updateBacktest', () => {
  it('patches the star', async () => {
    const fetch = stubApi({
      'PATCH /api/v1/backtests/bt_7f3k2m9qx4': { status: 200, body: backtest({ starred: true }) },
    });
    await expect(updateBacktest('bt_7f3k2m9qx4', { starred: true })).resolves.toMatchObject({ starred: true });
    expect(fetch.mock.calls[0]?.[1]?.body).toBe('{"starred":true}');
  });

  it('passes a backtest that is gone on as not-found', async () => {
    stubApi({ 'PATCH /api/v1/backtests/bt_7f3k2m9qx4': problem(404, 'not-found', 'No such backtest.') });
    await expect(updateBacktest('bt_7f3k2m9qx4', { starred: true })).rejects.toMatchObject({ status: 404 });
  });
});

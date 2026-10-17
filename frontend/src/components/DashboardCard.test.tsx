import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { DashboardCard } from './DashboardCard';

const classOf = (html: string) => /<section [^>]*class="([^"]*)"/.exec(html)?.[1]?.split(' ') ?? [];

describe('DashboardCard', () => {
  it('keeps 4 px between the parts of a card of Settings', () => {
    const html = renderToString(<DashboardCard title="Account">rows</DashboardCard>);
    expect(classOf(html)).toContain('gap-1');
  });

  it('lets the parts of a dashboard widget touch', () => {
    const html = renderToString(
      <DashboardCard title="Last backtests" flush>
        table
      </DashboardCard>,
    );
    expect(classOf(html)).not.toContain('gap-1');
  });
});

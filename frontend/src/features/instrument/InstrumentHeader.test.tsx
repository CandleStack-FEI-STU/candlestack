import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import type { InstrumentDetail } from '@/api';

import { InstrumentHeader } from './InstrumentHeader';

const AAPL: InstrumentDetail = {
  id: 'stock:AAPL',
  symbol: 'AAPL',
  name: 'Apple Inc.',
  market: 'stock',
  exchange: 'NASDAQ',
  source: 'alpaca',
  feed: 'iex',
  base: null,
  quote: null,
  available_from: null,
  available_to: 0,
  max_candles: 1000,
  timeframes: ['1d'],
};

describe('InstrumentHeader', () => {
  it('shows the 64 px icon before the name', () => {
    const html = renderToStaticMarkup(<InstrumentHeader instrument={AAPL} />);
    const icon = html.indexOf('<img ');
    expect(icon).toBeGreaterThan(-1);
    expect(html.slice(icon)).toMatch(/^<img [^>]*src="\/api\/v1\/data\/instruments\/stock%3AAAPL\/icon"/);
    expect(html.slice(icon)).toMatch(/^<img [^>]*width="64"/);
    expect(icon).toBeLessThan(html.indexOf('Apple Inc.'));
  });
});

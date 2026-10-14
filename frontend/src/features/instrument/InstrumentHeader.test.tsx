import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import type { InstrumentDetail } from '@/api';
import { classes } from '@/test/markup';

import { InstrumentHeader } from './InstrumentHeader';

const AAPL: InstrumentDetail = {
  id: 'stock:AAPL',
  symbol: 'AAPL',
  name: 'Apple Inc.',
  market: 'stock',
  exchange: 'NASDAQ',
  source: 'alpaca',
  feed: 'sip',
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

  it('keeps the symbol for screen readers on a phone and wraps a long id or name', () => {
    const html = renderToStaticMarkup(<InstrumentHeader instrument={AAPL} />);
    // On a phone the symbol ends the id above the name: its fact is only hidden from the screen.
    const symbol = classes(html, /<div [^>]*><dt[^>]*>Symbol</);
    expect(symbol).toContain('sr-only');
    expect(symbol).toContain('sm:not-sr-only');
    expect(symbol).not.toContain('hidden');
    expect(classes(html, /<div [^>]*><p[^>]*>stock:AAPL</)).toContain('min-w-0');
    expect(classes(html, /<p [^>]*>stock:AAPL</)).toContain('break-all');
    expect(classes(html, /<h1 [^>]*>Apple Inc\.</)).toContain('break-words');
  });
});

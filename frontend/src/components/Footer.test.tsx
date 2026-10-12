import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { Footer } from '@/components/Footer';

// #166: the chart has no TradingView logo, so the footer carries the attributions.
describe('Footer', () => {
  const html = renderToStaticMarkup(<Footer />);

  it('credits TradingView Lightweight Charts', () => {
    expect(html).toContain('Charts by');
    expect(html).toContain('<a href="https://www.tradingview.com/"');
    expect(html).toContain('TradingView Lightweight Charts™</a>');
  });

  it('credits Logo.dev for the instrument logos', () => {
    expect(html).toContain('Logos provided by');
    expect(html).toContain('<a href="https://logo.dev"');
    expect(html).toContain('Logo.dev</a>');
  });
});

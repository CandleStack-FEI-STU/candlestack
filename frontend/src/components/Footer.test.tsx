import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { Footer } from '@/components/Footer';

// The anchor whose text is `name`, with its attributes in any order.
function link(html: string, name: string): string {
  const attributes = new RegExp(`<a ([^>]*)>${name}</a>`).exec(html)?.[1];
  if (attributes === undefined) throw new Error(`no link "${name}"`);
  return attributes;
}

// #166: the chart has no TradingView logo, so the footer carries the attributions.
describe('Footer', () => {
  it('credits TradingView Lightweight Charts', () => {
    const html = renderToStaticMarkup(<Footer />);
    expect(html).toContain('Charts by');
    expect(link(html, 'TradingView Lightweight Charts™')).toContain('href="https://www.tradingview.com/"');
  });

  it('credits Logo.dev for the instrument logos', () => {
    const html = renderToStaticMarkup(<Footer />);
    expect(html).toContain('Logos provided by');
    expect(link(html, 'Logo.dev')).toContain('href="https://logo.dev"');
  });

  it('opens the credits in a new tab without an opener', () => {
    const html = renderToStaticMarkup(<Footer />);
    for (const name of ['TradingView Lightweight Charts™', 'Logo.dev']) {
      expect(link(html, name)).toContain('target="_blank"');
      expect(link(html, name)).toContain('rel="noreferrer"');
    }
  });
});

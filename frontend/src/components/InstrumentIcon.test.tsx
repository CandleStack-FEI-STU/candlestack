import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { IconTile, InstrumentIcon } from '@/components/InstrumentIcon';

// The attributes of the first element `tag`, in any order.
function element(html: string, tag: string): string {
  const attributes = new RegExp(`<${tag} ([^>]*)>`).exec(html)?.[1];
  if (attributes === undefined) throw new Error(`no <${tag}>`);
  return attributes;
}

// #179: the same icon in the list, the header search and on the instrument page.
describe('InstrumentIcon', () => {
  it("shows the instrument's icon from the API", () => {
    const img = element(renderToStaticMarkup(<InstrumentIcon id="stock:BRK.B" size={32} />), 'img');
    expect(img).toContain('src="/api/v1/data/instruments/stock%3ABRK.B/icon"');
  });

  it('keeps its size while the image loads and only loads it when it is near the screen', () => {
    const img = element(renderToStaticMarkup(<InstrumentIcon id="crypto:BTCUSDT" size={64} />), 'img');
    expect(img).toContain('width="64"');
    expect(img).toContain('height="64"');
    expect(img).toContain('loading="lazy"');
  });

  it('has an empty alt, since the symbol is next to it', () => {
    const img = element(renderToStaticMarkup(<InstrumentIcon id="crypto:BTCUSDT" size={32} />), 'img');
    expect(img).toContain('alt=""');
  });

  it('sits on a white tile rounded by a tenth of its size, in both themes', () => {
    for (const [size, box] of [
      [32, 'size-8'],
      [64, 'size-16'],
    ] as const) {
      const tile = element(renderToStaticMarkup(<InstrumentIcon id="crypto:BTCUSDT" size={size} />), 'span');
      expect(tile).toContain(box);
      expect(tile).toContain('rounded-[10%]');
      expect(tile).toContain('bg-white');
      expect(tile).not.toContain('dark:');
    }
  });

  it('keeps a logo that fills its box inside the tile, under the hairline', () => {
    const html = renderToStaticMarkup(<InstrumentIcon id="stock:AAPL" size={64} />);
    expect(element(html, 'span')).toContain('overflow-hidden');
    expect(element(html, 'span')).toMatch(/after:absolute .*after:inset-ring /);
    expect(element(html, 'img')).toMatch(/absolute inset-px size-\[calc\(100%-2px\)\] .*object-contain/);
  });

  it("draws the backend's fallback itself when the image does not load", () => {
    const html = renderToStaticMarkup(<IconTile id="stock:AAPL" size={32} failed onError={() => {}} />);
    expect(html).not.toContain('<img');
    expect(html).toContain('bg-icon-fallback');
    expect(html).toContain('lucide-chart-candlestick');
  });

  it('shows the image until it failed', () => {
    const html = renderToStaticMarkup(<IconTile id="stock:AAPL" size={32} failed={false} onError={() => {}} />);
    expect(html).toContain('<img');
    expect(html).not.toContain('lucide-chart-candlestick');
  });
});

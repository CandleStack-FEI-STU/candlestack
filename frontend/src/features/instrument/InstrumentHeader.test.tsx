import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import type { InstrumentDetail } from '@/api';
import { NEW_YORK } from '@/lib/dates';
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

const STYLE = { timeZone: NEW_YORK, dateFormat: 'dmy', timeFormat: '24' } as const;

describe('InstrumentHeader', () => {
  it('shows the 64 px icon before the name', () => {
    const html = renderToStaticMarkup(<InstrumentHeader instrument={AAPL} dateStyle={STYLE} />);
    const icon = html.indexOf('<img ');
    expect(icon).toBeGreaterThan(-1);
    expect(html.slice(icon)).toMatch(/^<img [^>]*src="\/api\/v1\/data\/instruments\/stock%3AAAPL\/icon"/);
    expect(html.slice(icon)).toMatch(/^<img [^>]*width="64"/);
    expect(icon).toBeLessThan(html.indexOf('Apple Inc.'));
  });

  it('shows the four facts on every screen, wrapping as the mockup does, and wraps a long id or name', () => {
    const html = renderToStaticMarkup(<InstrumentHeader instrument={AAPL} dateStyle={STYLE} />);
    expect(
      [...html.matchAll(/<dt[^>]*>([^<]*)<\/dt><dd[^>]*>([^<]*)</g)].map(([, label, value]) => [label, value]),
    ).toEqual([
      ['Symbol', 'AAPL'],
      ['Exchange', 'NASDAQ'],
      ['Source', 'alpaca (sip)'],
      ['Data since', 'unknown'],
    ]);
    expect(html).not.toContain('sr-only');
    expect(classes(html, /<dl [^>]*>/)).toEqual(expect.arrayContaining(['flex-wrap', 'gap-x-10', 'gap-y-3']));
    expect(classes(html, /<div [^>]*><p[^>]*>stock:AAPL</)).toContain('min-w-0');
    expect(classes(html, /<p [^>]*>stock:AAPL</)).toContain('break-all');
    expect(classes(html, /<h1 [^>]*>Apple Inc\.</)).toContain('break-words');
  });

  it("writes the first day in the user's date format, as the day it was in the chart's zone", () => {
    // 2020-07-28 02:00 UTC is still 27 July in New York, already 28 July in Bratislava.
    const listed = { ...AAPL, available_from: Date.UTC(2020, 6, 28, 2) / 1000 };
    const since = (dateStyle: typeof STYLE | { timeZone: string; dateFormat: 'iso'; timeFormat: '24' }) =>
      renderToStaticMarkup(<InstrumentHeader instrument={listed} dateStyle={dateStyle} />);
    expect(since(STYLE)).toContain('27 Jul 2020');
    expect(since({ ...STYLE, dateFormat: 'iso' })).toContain('2020-07-27');
    expect(since({ timeZone: 'Europe/Bratislava', dateFormat: 'iso', timeFormat: '24' })).toContain('2020-07-28');
  });
});

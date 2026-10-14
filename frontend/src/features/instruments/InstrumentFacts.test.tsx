import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { InstrumentFacts } from './InstrumentFacts';

describe('InstrumentFacts', () => {
  it('shows the four facts, no more instruments than the API has', () => {
    const facts = [
      ...renderToStaticMarkup(<InstrumentFacts />).matchAll(/<li [^>]*><b [^>]*>([^<]+)<\/b> ([^<]+)<\/li>/g),
    ];
    expect(facts.map(([, value, label]) => `${value} ${label}`)).toEqual([
      '14,000+ instruments',
      '1m – 1d candles',
      'Jan 2016 first stock candles',
      'Since listing for crypto pairs',
    ]);
  });
});

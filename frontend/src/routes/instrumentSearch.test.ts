import { describe, expect, it } from 'vitest';

import { validateInstrumentSearch } from './instrumentSearch';

// The router passes the raw search object; SearchSchemaInput is only a type marker.
type RawSearch = Parameters<typeof validateInstrumentSearch>[0];
const validate = (search: Record<string, unknown>) => validateInstrumentSearch(search as RawSearch);

describe('validateInstrumentSearch', () => {
  it('keeps a valid timeframe', () => {
    expect(validate({ tf: '4h' })).toEqual({ tf: '4h' });
  });

  it('fills in the default when tf is missing or broken', () => {
    expect(validate({})).toEqual({ tf: '1h' });
    expect(validate({ tf: 'banana' })).toEqual({ tf: '1h' });
  });

  it('drops params the route does not know', () => {
    expect(validate({ tf: '1d', extra: 'x' })).toEqual({ tf: '1d' });
  });
});

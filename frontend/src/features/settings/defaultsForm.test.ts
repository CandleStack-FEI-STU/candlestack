import { describe, expect, it } from 'vitest';

import { DEFAULT_PREFERENCES } from '@/test/api';

import { checkDefaults, formOf, sameDefaults, type DefaultsForm } from './defaultsForm';

const SAVED = DEFAULT_PREFERENCES.backtest_defaults;
const FORM = formOf(SAVED);

describe('the Backtest defaults form', () => {
  it('starts from the saved defaults, the percentages as text', () => {
    expect(FORM.fees_pct).toBe('0.1');
    expect(FORM.slippage_pct).toBe('0.02');
    expect(checkDefaults(FORM)).toEqual({ defaults: SAVED, invalid: new Set() });
  });

  it('reads the percentages, with a comma too, from 0 to 5', () => {
    expect(checkDefaults({ ...FORM, fees_pct: ' 0,25 ', slippage_pct: '5' }).defaults).toMatchObject({
      fees_pct: 0.25,
      slippage_pct: 5,
    });
    expect(checkDefaults({ ...FORM, fees_pct: '0' }).defaults?.fees_pct).toBe(0);
    expect(checkDefaults({ ...FORM, fees_pct: '.5' }).defaults?.fees_pct).toBe(0.5);
    for (const bad of ['', '.', '5.01', '-1', '1e2', 'abc', '0x1']) {
      expect(checkDefaults({ ...FORM, slippage_pct: bad }).invalid).toEqual(new Set(['slippage_pct']));
    }
  });

  it('takes days that exist, as YYYY-MM-DD', () => {
    expect(checkDefaults({ ...FORM, period_start: '2024-02-29' }).defaults?.period_start).toBe('2024-02-29');
    for (const bad of ['2023-02-29', '2021-13-01', '2021-1-4', '04.01.2021', '']) {
      const { defaults, invalid } = checkDefaults({ ...FORM, period_start: bad });
      expect(defaults).toBeUndefined();
      expect(invalid).toEqual(new Set(['period_start']));
    }
    expect(checkDefaults({ ...FORM, period_start: 'x', period_end: 'y' }).invalid).toEqual(
      new Set(['period_start', 'period_end']),
    );
  });

  it('wants the test period to end after it starts', () => {
    expect(checkDefaults({ ...FORM, period_end: '2021-01-04' }).invalid).toEqual(new Set(['period_end']));
    expect(checkDefaults({ ...FORM, period_end: '2020-12-31' }).invalid).toEqual(new Set(['period_end']));
    expect(checkDefaults({ ...FORM, period_end: '2021-01-05' }).invalid.size).toBe(0);
  });

  it('sends the nine fields and nothing else, even when the form holds more', () => {
    const form = { ...FORM, extra: 'kept out' } as DefaultsForm;
    expect(Object.keys(checkDefaults(form).defaults ?? {}).sort()).toEqual(Object.keys(SAVED).sort());
  });

  it('tells a change from the saved defaults', () => {
    expect(sameDefaults(SAVED, { ...SAVED })).toBe(true);
    expect(sameDefaults(SAVED, { ...SAVED, threshold: 0.06 })).toBe(false);
    expect(sameDefaults(SAVED, { ...SAVED, benchmark: 'SPY' })).toBe(false);
  });
});

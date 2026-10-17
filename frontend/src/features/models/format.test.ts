import { describe, expect, it } from 'vitest';

import type { DateFormat } from '@/api';

import {
  formatAdded,
  formatMegabytes,
  formatParameters,
  formatShape,
  formatSharpe,
  formatSize,
  formatUsage,
  plural,
  splitExtension,
} from './format';
import { ACCEPTED_EXTENSIONS, frameworkOfFile } from './frameworks';

const MB = 1024 * 1024;

describe('formatSize', () => {
  it('writes binary megabytes with one decimal', () => {
    expect(formatSize(14_889_779)).toBe('14.2 MB');
    expect(formatSize(3 * MB)).toBe('3.0 MB');
    expect(formatSize(50 * MB)).toBe('50.0 MB');
  });

  it('never writes 0.0 MB for a file that is not empty', () => {
    expect(formatSize(2_000)).toBe('0.1 MB');
    expect(formatSize(0)).toBe('0.0 MB');
  });
});

describe('formatMegabytes and formatUsage', () => {
  it('drop a trailing zero, as the storage line writes it', () => {
    expect(formatMegabytes(0)).toBe('0');
    expect(formatMegabytes(29.5 * MB)).toBe('29.5');
    expect(formatMegabytes(100 * MB)).toBe('100');
    expect(formatUsage(Math.round(14.2 * MB), 100 * MB)).toBe('14.2 MB of 100 MB');
  });
});

describe('formatParameters', () => {
  it('writes millions with 2 decimals from 100,000', () => {
    expect(formatParameters(1_240_000)).toBe('1.24 M');
    expect(formatParameters(100_000)).toBe('0.10 M');
    expect(formatParameters(12_345_678)).toBe('12.35 M');
  });

  it('writes grouped digits below it', () => {
    expect(formatParameters(9_325)).toBe('9,325');
    expect(formatParameters(99_999)).toBe('99,999');
    expect(formatParameters(0)).toBe('0');
  });
});

describe('formatShape', () => {
  it('joins the input with × and adds the output after an arrow', () => {
    expect(formatShape([25, 23], [1])).toBe('25×23 → 1');
    expect(formatShape([25, 23], [1], true)).toBe('25 × 23 → 1');
    expect(formatShape([30, 23, 4], [3, 2], true)).toBe('30 × 23 × 4 → 3 × 2');
  });

  it('leaves out an unknown output, and says nothing without an input', () => {
    expect(formatShape([25, 23], null)).toBe('25×23');
    expect(formatShape(null, [1])).toBeNull();
    expect(formatShape([], [1])).toBeNull();
  });
});

describe('formatSharpe', () => {
  it('writes 2 decimals with a real minus sign, an en dash without a value', () => {
    expect(formatSharpe(1.344)).toBe('1.34');
    expect(formatSharpe(-0.18)).toBe('−0.18');
    expect(formatSharpe(0)).toBe('0.00');
    expect(formatSharpe(null)).toBe('–');
  });
});

describe('formatAdded', () => {
  const now = new Date('2026-10-17T12:00:00Z');
  const utc = (dateFormat: DateFormat) => ({ timeZone: 'UTC', dateFormat });

  it('says Today for a model added today, in every date format', () => {
    for (const format of ['dmy', 'iso', 'dot'] as const) {
      expect(formatAdded('2026-10-17T00:30:00Z', utc(format), now)).toBe('Today');
    }
  });

  it('writes an earlier day of this year as day and month in the default format', () => {
    expect(formatAdded('2026-10-13T09:00:00Z', utc('dmy'), now)).toBe('13 Oct');
    expect(formatAdded('2025-12-31T09:00:00Z', utc('dmy'), now)).toBe('31 Dec 2025');
  });

  it('writes the whole date in the numeric formats', () => {
    expect(formatAdded('2026-10-13T09:00:00Z', utc('iso'), now)).toBe('2026-10-13');
    expect(formatAdded('2026-10-13T09:00:00Z', utc('dot'), now)).toBe('13.10.2026');
  });

  it('counts days in the zone of the setting', () => {
    // 23:30 on 16 Oct in UTC is already 17 Oct in Bratislava, and still 16 Oct in New York.
    const day = '2026-10-16T23:30:00Z';
    expect(formatAdded(day, { timeZone: 'Europe/Bratislava', dateFormat: 'dmy' }, now)).toBe('Today');
    expect(formatAdded(day, { timeZone: 'America/New_York', dateFormat: 'dmy' }, now)).toBe('16 Oct');
  });
});

describe('plural and splitExtension', () => {
  it('count with the right noun', () => {
    expect(plural(1, 'model')).toBe('1 model');
    expect(plural(0, 'model')).toBe('0 models');
    expect(plural(3, 'backtest')).toBe('3 backtests');
  });

  it('split the stem from the last extension', () => {
    expect(splitExtension('my-tsmixer.keras')).toEqual(['my-tsmixer', '.keras']);
    expect(splitExtension('v1.2.keras')).toEqual(['v1.2', '.keras']);
    expect(splitExtension('.keras')).toEqual(['.keras', '']);
    expect(splitExtension('model')).toEqual(['model', '']);
  });
});

describe('frameworkOfFile', () => {
  it('knows a framework by the file extension, in any case', () => {
    expect(frameworkOfFile('lstm.keras')).toBe('Keras');
    expect(frameworkOfFile('LSTM.KERAS')).toBe('Keras');
    expect(frameworkOfFile('tcn.pt')).toBe('PyTorch');
    expect(frameworkOfFile('tcn.pth')).toBe('PyTorch');
    expect(frameworkOfFile('mixer.onnx')).toBe('ONNX');
    expect(frameworkOfFile('old.h5')).toBe('TensorFlow');
    expect(frameworkOfFile('saved.pb')).toBe('TensorFlow');
    expect(frameworkOfFile('saved.zip')).toBe('TensorFlow');
    expect(frameworkOfFile('gbm.joblib')).toBe('scikit-learn');
    expect(frameworkOfFile('gbm.pkl')).toBe('scikit-learn');
    expect(frameworkOfFile('gbm.skops')).toBe('scikit-learn');
  });

  it('knows no framework for any other file', () => {
    expect(frameworkOfFile('notes.txt')).toBeNull();
    expect(frameworkOfFile('keras')).toBeNull();
  });

  it('lets the file picker offer every extension', () => {
    expect(ACCEPTED_EXTENSIONS).toBe('.keras,.h5,.pb,.zip,.pt,.pth,.onnx,.joblib,.pkl,.skops');
  });
});

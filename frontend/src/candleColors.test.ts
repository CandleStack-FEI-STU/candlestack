/// <reference types="node" />
import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

// Read as a file: Vitest does not load CSS into tests.
const css = readFileSync(new URL('index.css', import.meta.url), 'utf8');

// #113: the candles must not look like the teal accent, and must stay visible on the page.

function variable(block: string, name: string): string {
  const value = new RegExp(`--${name}:\\s*(#[0-9a-f]{6})`, 'i').exec(block)?.[1];
  if (!value) throw new Error(`--${name} is missing`);
  return value;
}

function channels(hex: string): [number, number, number] {
  const value = Number.parseInt(hex.slice(1), 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

// The hue in degrees, 0 to 360.
function hue(hex: string): number {
  const [r, g, b] = channels(hex).map((c) => c / 255) as [number, number, number];
  const max = Math.max(r, g, b);
  const d = max - Math.min(r, g, b);
  if (d === 0) return 0;
  const h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return (h * 60 + 360) % 360;
}

// WCAG contrast ratio; 3:1 is the minimum for graphics.
function contrast(a: string, b: string): number {
  const luminance = (hex: string) => {
    const [r, g, bl] = channels(hex).map((c) => {
      const v = c / 255;
      return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    }) as [number, number, number];
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
  };
  const [hi, lo] = [luminance(a), luminance(b)].toSorted((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

const light = css.slice(css.indexOf(':root {'), css.indexOf(":root[data-theme='dark']"));
const dark = css.slice(css.indexOf(":root[data-theme='dark']"));

describe.each([
  ['light', light],
  ['dark', dark],
])('candle colors in the %s theme', (_, block) => {
  it('keep the up color at least 30° of hue away from the teal accent', () => {
    expect(Math.abs(hue(variable(block, 'candle-up')) - hue(variable(block, 'accent')))).toBeGreaterThanOrEqual(30);
  });

  it('stand out from the background at 3:1 or more', () => {
    const bg = variable(block, 'bg');
    expect(contrast(variable(block, 'candle-up'), bg)).toBeGreaterThanOrEqual(3);
    expect(contrast(variable(block, 'candle-down'), bg)).toBeGreaterThanOrEqual(3);
  });
});

import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import type { Provider } from '@/api';
import { classes } from '@/test/markup';

import { ProviderButton } from './ProviderButton';

const render = (provider: Provider, busy: Provider | null) =>
  renderToStaticMarkup(<ProviderButton provider={provider} busy={busy} onStart={() => undefined} />);

describe('ProviderButton', () => {
  it('continues with the provider, its mark before the name', () => {
    const html = render('github', null);
    expect(html).toMatch(
      /<button [^>]*type="button"[^>]*><svg [^>]*>.*<\/svg><span>Continue with GitHub<\/span><\/button>/,
    );
    expect(html).not.toContain('disabled=""');
    expect(render('google', null)).toContain('<span>Continue with Google</span>');
  });

  it('sets its 15 px label in the line height of the font, as the design does', () => {
    expect(classes(render('github', null), /<button [^>]*>/)).toContain('text-[15px]/[normal]');
  });

  it('shows the clicked one busy: disabled but solid, a spinner instead of the mark', () => {
    const html = render('github', 'github');
    expect(html).toContain('<span>Opening GitHub</span>');
    expect(html).toContain('disabled=""');
    expect(classes(html, /<button [^>]*>/)).toContain('disabled:opacity-100');
    // The design's spinner: a 16 px ring open on the right, turning every 0.7 s, left of the text.
    expect(classes(html, /<span aria-hidden="true"[^>]*>/)).toEqual(
      expect.arrayContaining([
        'absolute',
        'left-[calc(50%-82px)]',
        'size-4',
        'animate-[spin_0.7s_linear_infinite]',
        'rounded-full',
        'border-2',
        'border-current',
        'border-r-transparent',
      ]),
    );
    // The mark keeps its place, so the text does not move.
    expect(html).toContain('<svg viewBox="0 0 24 24" aria-hidden="true" class="size-[18px] invisible">');
  });

  it('dims the other one while the first loads', () => {
    const html = render('google', 'github');
    expect(html).toContain('<span>Continue with Google</span>');
    expect(html).toContain('disabled=""');
    expect(classes(html, /<button [^>]*>/)).not.toContain('disabled:opacity-100');
    expect(html).not.toContain('animate-[spin');
  });

  it('stops the spinner for people who ask for less motion', () => {
    expect(render('google', 'google')).toContain('motion-reduce:animate-none');
  });
});

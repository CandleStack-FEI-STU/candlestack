import { describe, expect, it } from 'vitest';

import { nameOf, nameProblem } from './names';

describe('nameOf', () => {
  it('strips the whitespace the API strips, U+0085 and the ideographic space too', () => {
    expect(nameOf(' \t lstm v2 \u0085\u3000\u00a0')).toBe('lstm v2');
  });

  it('keeps what the API keeps and then refuses: the information separators and U+FEFF', () => {
    expect(nameOf('\u001clstm\u001f')).toBe('\u001clstm\u001f');
    expect(nameOf('\ufefflstm')).toBe('\ufefflstm');
  });
});

describe('nameProblem', () => {
  it('takes a plain name', () => {
    expect(nameProblem('lstm-v2 (final)')).toBeUndefined();
  });

  it('refuses slashes and invisible characters', () => {
    expect(nameProblem('lstm/v2')).toBe('Names cannot contain / or \\.');
    expect(nameProblem('lstm\\v2')).toBe('Names cannot contain / or \\.');
    expect(nameProblem(nameOf('\u001clstm'))).toBe('Names cannot contain invisible characters such as tabs.');
    expect(nameProblem(nameOf('\ufefflstm'))).toBe('Names cannot contain invisible characters such as tabs.');
  });

  it('counts the length in code points, as the API does', () => {
    expect(nameProblem('😀'.repeat(60))).toBeUndefined();
    expect(nameProblem('😀'.repeat(61))).toBe('Names can be up to 60 characters.');
    expect(nameProblem('a'.repeat(61))).toBe('Names can be up to 60 characters.');
  });
});

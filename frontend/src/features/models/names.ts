// A model's name as Rename edits it, by the rules of the API (ModelUpdate in
// backend/src/candlestack/ml/schemas.py), so the dialog is neither stricter nor looser than it.

// As the API takes it: 1 to 60 characters before the extension.
const NAME_MAX = 60;

// The name as the API reads it: without the whitespace at its ends that pydantic strips, which is
// Unicode White_Space (U+0085 too, which String.trim keeps, but not U+FEFF, which String.trim
// strips and the API refuses as a format character).
export const nameOf = (text: string) => text.replace(/^\p{White_Space}+|\p{White_Space}+$/gu, '');

// What the API refuses in a name, said before Save instead of after a round trip: slashes,
// control and format characters (Unicode Cc and Cf: tabs, zero-width spaces, direction marks) and
// more than 60 characters, counted in code points as the API counts them.
export function nameProblem(name: string): string | undefined {
  if (/[/\\]/.test(name)) return 'Names cannot contain / or \\.';
  if (/[\p{Cc}\p{Cf}]/u.test(name)) return 'Names cannot contain invisible characters such as tabs.';
  if (Array.from(name).length > NAME_MAX) return `Names can be up to ${NAME_MAX} characters.`;
  return undefined;
}

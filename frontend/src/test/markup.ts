// The classes of the first tag in `html` that matches `tag`, e.g. /<h1 [^>]*>/: tests check the
// classes that matter one by one, so a harmless reorder does not break them.
export function classes(html: string, tag: RegExp): string[] {
  return (html.match(tag)?.[0].match(/class="([^"]*)"/)?.[1] ?? '').split(' ');
}

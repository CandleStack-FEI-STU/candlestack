// @vitest-environment jsdom
import { RouterProvider, createMemoryHistory, createRootRoute, createRouter } from '@tanstack/react-router';
import { cleanup, render, screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';

import { Filters } from './Filters';

afterEach(cleanup);

// The open panel needs the browser APIs Radix measures with and the media query of its layout.
async function open() {
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  window.matchMedia ??= (query: string) =>
    ({ matches: true, media: query, addEventListener() {}, removeEventListener() {} }) as unknown as MediaQueryList;
  const rootRoute = createRootRoute({ component: () => <Filters market={undefined} exchange={undefined} /> });
  const router = createRouter({ routeTree: rootRoute, history: createMemoryHistory({ initialEntries: ['/'] }) });
  await router.load();
  render(<RouterProvider router={router} />);
  await userEvent.click(await screen.findByRole('button', { name: 'Filters: All instruments' }));
  return screen.getByRole('dialog', { name: 'Filters' });
}

describe('the Filters panel of the instrument list', () => {
  it('keeps the popover’s own motion and its tighter headings on a phone', async () => {
    const panel = await open();
    expect(panel.className).not.toMatch(/fx-pop/);
    expect(panel.className.split(' ')).toContain('data-[state=open]:animate-in');
    expect(screen.getByText('Type').className.split(' ')).toEqual(expect.arrayContaining(['mb-1', 'sm:mb-2']));
  });
});

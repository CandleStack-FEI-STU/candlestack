import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider, createMemoryHistory, createRootRoute, createRouter } from '@tanstack/react-router';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { classes } from '@/test/markup';

import { HomePage } from './HomePage';

// The page needs a router for its links and a query client for the most traded instruments.
async function render(): Promise<string> {
  const rootRoute = createRootRoute({ component: HomePage });
  const router = createRouter({ routeTree: rootRoute, history: createMemoryHistory({ initialEntries: ['/'] }) });
  await router.load();
  return renderToString(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

// The markup of the section with the given id.
function section(html: string, id: string): string {
  const match = new RegExp(`<section [^>]*id="${id}"[^>]*>.*?</section>`, 's').exec(html);
  if (match === null) throw new Error(`no section "${id}"`);
  return match[0];
}

describe('HomePage', () => {
  it('leads with the headline and puts the sections below it in the order of the design', async () => {
    const html = await render();
    expect(html).toMatch(/<h1 [^>]*>Backtest your models and compare every experiment<\/h1>/);
    const headings = [...html.matchAll(/<h2 [^>]*>([^<]*)<\/h2>/g)].map((match) => match[1]);
    expect(headings).toEqual([
      'Three layers you can swap',
      'US stocks and crypto pairs, candles from 1m to 1d',
      'Every run gets the same metrics',
      'A catalog of published experiments',
    ]);
  });

  it('links both Browse instruments buttons to the instrument list', async () => {
    const html = await render();
    const links = html.match(/<a [^>]*href="\/instruments"[^>]*>Browse instruments<\/a>/g);
    expect(links).toHaveLength(2);
    expect(section(html, 'markets')).toContain('>Browse instruments</a>');
  });

  it('shows Try Backtest as a button that does nothing yet, not a link', async () => {
    const html = await render();
    expect(html.match(/>Try Backtest</g)).toHaveLength(1);
    // Its attributes without the classes, whose disabled: styles are not the attribute.
    const button = (/<button [^>]*>Try Backtest<\/button>/.exec(html)?.[0] ?? '').replace(/class="[^"]*"/, '');
    expect(button).toContain('type="button"');
    expect(button).not.toContain('disabled');
    expect(html).not.toContain('<form');
  });

  it('marks compare and experiments as coming soon, over sketches screen readers skip', async () => {
    const html = await render();
    for (const id of ['compare', 'experiments']) {
      const markup = section(html, id);
      expect(markup.match(/>Coming soon<\/span>/g)).toHaveLength(1);
      expect(markup).toContain('aria-hidden="true"');
    }
    expect(html.match(/Coming soon/g)).toHaveLength(2);
  });

  it('counts the instruments as the API has them', async () => {
    const html = await render();
    expect(html).toContain('14,000+ stocks and pairs');
    expect(html).not.toContain('15,000');
  });

  it('lists the model frameworks a user can bring', async () => {
    const html = await render();
    const badges = [...section(html, 'layers').matchAll(/<li [^>]*>([^<]*)<\/li>/g)].map((match) => match[1]);
    expect(badges).toEqual(expect.arrayContaining(['Keras', 'TensorFlow', 'PyTorch', 'ONNX', 'scikit-learn']));
    expect(badges).toHaveLength(16);
  });

  it('stops the dashes on the pipeline when the user asks for less motion', async () => {
    const html = await render();
    const dash = classes(html, /<span [^>]*animate-pipeline-flow[^>]*>/);
    expect(dash).toContain('motion-reduce:animate-none');
    expect(dash).toContain('motion-reduce:left-1/2');
    expect(html.match(/animate-pipeline-flow/g)).toHaveLength(4);
  });
});

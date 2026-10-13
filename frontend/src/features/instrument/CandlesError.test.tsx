import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { ApiError } from '@/api';

import { CandlesError } from './CandlesError';

const PATH = 'Nothing at /api/v1/data/instruments/crypto:ETHUSDT/candles?timeframe=1h&limit=500.';

function render(error: Error) {
  const noop = () => undefined;
  return renderToStaticMarkup(
    <CandlesError error={error} errorAt={0} autoRetries={0} onRetry={noop} onAutoRetry={noop} />,
  );
}

describe('CandlesError', () => {
  // min-w-0 lets the message shrink in its flex row, break-words breaks the path inside the box.
  it('wraps a long message inside its box', () => {
    expect(render(new ApiError(404, PATH))).toMatch(/<p role="alert" class="min-w-0 break-words">Nothing at/);
  });

  it('wraps a long message while it counts down', () => {
    expect(render(new ApiError(429, PATH, { retryAfter: 30 }))).toMatch(
      /<output class="min-w-0 break-words">Nothing at/,
    );
  });
});

import type { SearchSchemaInput } from '@tanstack/react-router';

import { parseTimeframe, type Timeframe } from '@/api';

// What the page gets: every param has a value.
export type InstrumentSearch = { tf: Timeframe };

// What a link or a typed URL may pass: anything or nothing (SearchSchemaInput marks this type
// as the input side). A link without `search` is fine, and a broken link like ?tf=banana opens
// the default timeframe instead of breaking the page.
export function validateInstrumentSearch(search: { tf?: unknown } & SearchSchemaInput): InstrumentSearch {
  return { tf: parseTimeframe(search.tf) };
}

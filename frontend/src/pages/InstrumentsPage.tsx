import { useNavigate, useSearch } from '@tanstack/react-router';
import { useCallback, useEffect } from 'react';

import { PageTitle } from '@/components/PageTitle';
import { InstrumentList, MarketFilter, SearchBox, rememberListSearch } from '@/features/instruments';
import { usePageTitle } from '@/lib/usePageTitle';

// The start page: every stock and crypto pair, searchable. /?q=btc&market=crypto&page=2
export function InstrumentsPage() {
  const search = useSearch({ from: '/' });
  const { q = '', market, page = 1 } = search;
  const navigate = useNavigate({ from: '/' });
  // "Instruments" on an instrument page comes back to this search.
  useEffect(() => rememberListSearch(search), [search]);
  usePageTitle(q === '' ? 'Instruments' : `“${q}” · Instruments`);

  // A new query starts at page 1; typing replaces the history entry instead of adding one per pause.
  const onSearch = useCallback(
    (next: string) =>
      void navigate({ search: (prev) => ({ ...prev, q: next || undefined, page: undefined }), replace: true }),
    [navigate],
  );

  return (
    <>
      <PageTitle title="Instruments" description="US stocks and crypto pairs. Open one to see its candles." />
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <SearchBox query={q} onSearch={onSearch} />
        <MarketFilter current={market} />
      </div>
      <InstrumentList query={q} market={market} page={page} />
    </>
  );
}

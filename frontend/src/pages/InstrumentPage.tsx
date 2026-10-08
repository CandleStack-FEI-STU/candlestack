import { useParams, useSearch } from '@tanstack/react-router';

import { PageTitle } from '@/components/PageTitle';

// The instrument details and the candle chart come in #113.
export function InstrumentPage() {
  const { id } = useParams({ from: '/instrument/$id' });
  const { tf } = useSearch({ from: '/instrument/$id' });

  return <PageTitle title={id} description={`Timeframe ${tf}. Candle chart coming next.`} />;
}

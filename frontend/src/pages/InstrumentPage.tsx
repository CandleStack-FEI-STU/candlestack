import { useSuspenseQuery } from '@tanstack/react-query';
import { useParams, useSearch } from '@tanstack/react-router';

import { instrumentQueryOptions } from '@/api';
import { InstrumentCandles, InstrumentHeader, TimeframeSwitch } from '@/features/instrument';
import { usePageTitle } from '@/lib/usePageTitle';

// /instrument/crypto:BTCUSDT?tf=1h. The route loader has already fetched the instrument.
export function InstrumentPage() {
  const { id } = useParams({ from: '/instrument/$id' });
  const { tf } = useSearch({ from: '/instrument/$id' });
  const { data: instrument } = useSuspenseQuery(instrumentQueryOptions(id));
  usePageTitle(`${instrument.symbol} ${tf}`);

  return (
    <>
      <InstrumentHeader instrument={instrument} />
      <div className="mb-3">
        <TimeframeSwitch timeframes={instrument.timeframes} current={tf} />
      </div>
      <InstrumentCandles key={`${instrument.id}/${tf}`} instrument={instrument} timeframe={tf} />
    </>
  );
}

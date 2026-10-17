import { useSuspenseQuery } from '@tanstack/react-query';
import { useParams, useSearch } from '@tanstack/react-router';

import { instrumentQueryOptions, instrumentTimeframe } from '@/api';
import { InstrumentCandles, InstrumentHeader, TimeframeSwitch, marketTimeZone } from '@/features/instrument';
import { BackToList } from '@/features/instruments';
import { useDateStyle } from '@/features/preferences';
import { usePageTitle } from '@/lib/usePageTitle';

// /instrument/crypto:BTCUSDT?tf=1h. The route loader has already fetched the instrument.
export function InstrumentPage() {
  const { id } = useParams({ from: '/_public/instrument/$id' });
  const search = useSearch({ from: '/_public/instrument/$id' });
  const { data: instrument } = useSuspenseQuery(instrumentQueryOptions(id));
  // Only a timeframe the instrument has; otherwise its first one.
  const tf = instrumentTimeframe(search.tf, instrument.timeframes);
  // Signed in, the zone is the user's setting; a visitor sees the market's own.
  const dateStyle = useDateStyle(marketTimeZone(instrument.market));
  usePageTitle(`${instrument.symbol} ${tf}`);

  return (
    <>
      <BackToList />
      <InstrumentHeader instrument={instrument} dateStyle={dateStyle} />
      <div className="mb-3">
        <TimeframeSwitch timeframes={instrument.timeframes} current={tf} />
      </div>
      <InstrumentCandles key={`${instrument.id}/${tf}`} instrument={instrument} timeframe={tf} dateStyle={dateStyle} />
    </>
  );
}

import { useNavigate } from '@tanstack/react-router';

import { EXCHANGES, type Exchange } from '@/api';

// The exchange a stock is listed on, as a select: five values do not need five buttons. Like
// the market, it is part of the URL, and a new exchange starts at page 1.
export function ExchangeFilter({ current }: { current: Exchange | undefined }) {
  const navigate = useNavigate({ from: '/' });
  return (
    <select
      aria-label="Exchange"
      value={current ?? ''}
      onChange={(event) => {
        const exchange = EXCHANGES.find((value) => value === event.target.value);
        void navigate({ search: (prev) => ({ ...prev, exchange, page: undefined }), replace: true });
      }}
      className="h-[34px] rounded-md border bg-background px-2 text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
    >
      <option value="">All exchanges</option>
      {EXCHANGES.map((exchange) => (
        <option key={exchange} value={exchange}>
          {exchange}
        </option>
      ))}
    </select>
  );
}

import { useEffect } from 'react';

// "BTCUSDT · CandleStack" in the tab and in the browser history.
export function usePageTitle(title: string) {
  useEffect(() => {
    document.title = title ? `${title} · CandleStack` : 'CandleStack';
  }, [title]);
}

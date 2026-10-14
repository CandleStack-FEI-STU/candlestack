import { Link, useRouterState } from '@tanstack/react-router';
import { ArrowLeft } from 'lucide-react';

import { lastListSearch } from './lastSearch';

const LINK =
  'mb-4 inline-flex items-center gap-1.5 self-start rounded-md text-sm text-muted-foreground hover:text-foreground';

// "← Instruments" above an instrument: back to the list, with the search the user came from.
// Opened from the home page (its link sets from: 'home' in the history state), "← Home" instead.
export function BackToList() {
  const fromHome = useRouterState({ select: (state) => state.location.state.from === 'home' });
  if (fromHome) {
    return (
      <Link to="/" className={LINK}>
        <ArrowLeft className="size-4" />
        Home
      </Link>
    );
  }
  return (
    <Link to="/instruments" search={lastListSearch()} className={LINK}>
      <ArrowLeft className="size-4" />
      Instruments
    </Link>
  );
}

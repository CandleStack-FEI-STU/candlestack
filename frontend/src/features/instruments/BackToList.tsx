import { Link } from '@tanstack/react-router';
import { ArrowLeft } from 'lucide-react';

import { lastListSearch } from './lastSearch';

// "← Instruments" above an instrument: back to the list, with the search the user came from.
export function BackToList() {
  return (
    <Link
      to="/"
      search={lastListSearch()}
      className="mb-4 inline-flex items-center gap-1.5 rounded-md text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="size-4" />
      Instruments
    </Link>
  );
}

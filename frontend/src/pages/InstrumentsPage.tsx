import { PageTitle } from '@/components/PageTitle';
import { usePageTitle } from '@/lib/usePageTitle';

// The instrument list and search come in #112.
export function InstrumentsPage() {
  usePageTitle('Instruments');
  return <PageTitle title="Instruments" description="Stocks and crypto pairs. The list comes next." />;
}

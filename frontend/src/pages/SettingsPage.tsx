import { PageTitle } from '@/components/PageTitle';
import { usePageTitle } from '@/lib/usePageTitle';

// The account and the backtest defaults (#208): the title for now; the sections follow.
export function SettingsPage() {
  usePageTitle('Settings');
  return <PageTitle variant="workspace" title="Settings" description="Your account and how new backtests start" />;
}

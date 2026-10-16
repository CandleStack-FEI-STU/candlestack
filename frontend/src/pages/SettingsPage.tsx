import { WorkspaceTitle } from '@/features/workspace';
import { usePageTitle } from '@/lib/usePageTitle';

// The account and the backtest defaults (#208): the title for now; the sections follow.
export function SettingsPage() {
  usePageTitle('Settings');
  return <WorkspaceTitle title="Settings" lead="Your account and how new backtests start" />;
}

import { WorkspaceTitle } from '@/features/workspace';
import { usePageTitle } from '@/lib/usePageTitle';

// The user's backtests (#208): the title for now; the count, the search and the table follow.
export function BacktestsPage() {
  usePageTitle('Backtests');
  return <WorkspaceTitle title="Backtests" />;
}

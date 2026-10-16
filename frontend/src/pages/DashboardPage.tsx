import { useSignedInUser } from '@/features/account';
import { WorkspaceTitle } from '@/features/workspace';
import { usePageTitle } from '@/lib/usePageTitle';

// The start page after signing in. The greeting has the full name and no count under it: the
// widgets below it (#208) carry the numbers. "Welcome", not the design's "Welcome back": nobody
// has a backtest yet, so every visit is the design's new account.
export function DashboardPage() {
  const user = useSignedInUser();
  usePageTitle('Dashboard');
  return <WorkspaceTitle title={`Welcome, ${user.display_name}`} />;
}

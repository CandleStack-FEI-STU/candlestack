import { PageTitle } from '@/components/PageTitle';
import { useSignedInUser } from '@/features/account';
import { usePageTitle } from '@/lib/usePageTitle';

// The start page after signing in. The greeting has the full name and no count under it: the
// widgets below it (#208) carry the numbers.
export function DashboardPage() {
  const user = useSignedInUser();
  usePageTitle('Dashboard');
  return <PageTitle variant="workspace" title={`Welcome back, ${user.display_name}`} />;
}

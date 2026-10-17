import { PageTitle } from '@/components/PageTitle';
import { useSignedInUser } from '@/features/account';
import { useDashboard } from '@/features/backtests';
import { DashboardWidgets } from '@/features/dashboard';
import { useModels } from '@/features/models';
import { usePageTitle } from '@/lib/usePageTitle';

// The start page after signing in (mockups/app, ddDash). The greeting has the full name and no
// count under it: the widgets carry the numbers. A new account, without backtests, is welcomed
// instead of welcomed back. Until the dashboard has loaded the greeting waits, so a new account
// never sees "Welcome back" for a moment; when it cannot load, the greeting says why under it.
export function DashboardPage() {
  const user = useSignedInUser();
  usePageTitle('Dashboard');
  const { data, error } = useDashboard();
  const models = useModels().data?.models;
  if (!data) {
    return (
      <PageTitle
        variant="workspace"
        title={error ? `Welcome back, ${user.display_name}` : '\u00a0'}
        description={error?.message}
      />
    );
  }
  const full = data.counts.all > 0;
  return (
    <>
      <PageTitle
        variant="workspace"
        title={full ? `Welcome back, ${user.display_name}` : `Welcome, ${user.display_name}`}
        description={full ? undefined : 'Your account is ready.'}
      />
      <DashboardWidgets dashboard={data} models={models} />
    </>
  );
}

import { useParams } from '@tanstack/react-router';

import { PageTitle } from '@/components/PageTitle';
import { SettingsSectionView, SettingsTabs } from '@/features/settings';
import { usePageTitle } from '@/lib/usePageTitle';
import { FIRST_SECTION, isSettingsSection } from '@/routes/settingsSections';

// /settings/<section>: the account and how new backtests start, a section at a time under the
// tabs. The route has sent an unknown section to the first.
export function SettingsPage() {
  const section = useParams({
    from: '/_app/settings/$section',
    select: (params) => (isSettingsSection(params.section) ? params.section : FIRST_SECTION),
  });
  usePageTitle('Settings');
  return (
    <>
      <PageTitle variant="workspace" title="Settings" description="Your account and how new backtests start" />
      <SettingsTabs />
      <SettingsSectionView section={section} />
    </>
  );
}

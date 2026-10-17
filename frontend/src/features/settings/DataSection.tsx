import { DashboardCard } from '@/components/DashboardCard';
import { DataIcon } from '@/components/icons';
import { useDashboard } from '@/features/backtests';
import { formatUsage, StorageMeter, useModels } from '@/features/models';

import { SettingsRow } from './rows';

// How many backtests the account keeps, the count the sidebar shows. Only once the API has said.
function BacktestsRow() {
  const count = useDashboard().data?.counts.all;
  if (count === undefined) return null;
  return (
    <SettingsRow label="Backtests" hint="Kept until you delete them">
      <span className="font-mono">{count}</span>
    </SettingsRow>
  );
}

// The storage the uploaded models take (.st-meter): the megabytes over a 6 px meter, 260 px at
// most, how many there are under the label. Only once the API has said.
function ModelsRow() {
  const data = useModels().data;
  if (!data) return null;
  const { usage } = data;
  return (
    <SettingsRow label="Models" hint={`${data.models.length} uploaded`}>
      <div className="flex max-w-[260px] flex-col gap-1.5">
        <span className="font-mono">{formatUsage(usage.used_bytes, usage.quota_bytes)}</span>
        <StorageMeter usage={usage} />
      </div>
    </SettingsRow>
  );
}

// Where the candles come from and what the account keeps.
export function DataSection() {
  return (
    <DashboardCard icon={DataIcon} title="Data and storage">
      <SettingsRow label="Market data" hint="Delayed 15 min">
        <span>Alpaca, SIP feed</span>
      </SettingsRow>
      <BacktestsRow />
      <ModelsRow />
    </DashboardCard>
  );
}

import { DataIcon } from '@/components/icons';

import { SettingsCard, SettingsRow } from './Card';

// Where the candles come from. What the account keeps (backtests, models) joins it with those
// pages.
export function DataSection() {
  return (
    <SettingsCard icon={DataIcon} title="Data and storage">
      <SettingsRow label="Market data" hint="Delayed 15 min">
        <span>Alpaca, SIP feed</span>
      </SettingsRow>
    </SettingsCard>
  );
}

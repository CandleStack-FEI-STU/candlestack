import type { ComponentType } from 'react';

import type { SettingsSection } from '@/routes/settingsSections';

import { AccountSection } from './AccountSection';
import { ApiSection } from './ApiSection';
import { AppearanceSection } from './AppearanceSection';
import { BacktestDefaultsSection } from './BacktestDefaultsSection';
import { DataSection } from './DataSection';
import { ProfileSection } from './ProfileSection';
import { SignInSection } from './SignInSection';

const SECTIONS: Record<SettingsSection, ComponentType> = {
  profile: ProfileSection,
  'sign-in': SignInSection,
  'backtest-defaults': BacktestDefaultsSection,
  appearance: AppearanceSection,
  'data-and-storage': DataSection,
  'api-and-mcp': ApiSection,
  account: AccountSection,
};

// One section at a time, at most 720 px wide, its cards 16 px apart. A newly opened section fades
// up 6 px (keyed by its name, so only the section moves, not the tabs).
export function SettingsSectionView({ section }: { section: SettingsSection }) {
  const Section = SECTIONS[section];
  return (
    <div
      key={section}
      className="flex max-w-[720px] animate-in flex-col gap-4 duration-200 ease-out fade-in slide-in-from-bottom-[6px] motion-reduce:animate-none"
    >
      <Section />
    </div>
  );
}

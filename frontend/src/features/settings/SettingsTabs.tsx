import { Link } from '@tanstack/react-router';

import { SETTINGS_SECTIONS, type SettingsSection } from '@/routes/settingsSections';

const SECTION_LABELS: Record<SettingsSection, string> = {
  profile: 'Profile',
  'sign-in': 'Sign-in',
  'backtest-defaults': 'Backtest defaults',
  appearance: 'Appearance',
  'data-and-storage': 'Data and storage',
  'api-and-mcp': 'API and MCP',
  account: 'Account',
};

// The sections as tabs over a line (mockups/app, .st-tabs): each a link to its section, muted, ink
// on hover; the open one ink and medium with a 2 px accent line on the rule (the link marks it
// with data-status and aria-current).
const TAB =
  "relative px-3 pt-[9px] pb-[11px] text-sm/[normal] whitespace-nowrap text-muted-foreground transition-colors duration-150 hover:text-foreground data-[status=active]:font-medium data-[status=active]:text-foreground data-[status=active]:after:absolute data-[status=active]:after:inset-x-2.5 data-[status=active]:after:-bottom-px data-[status=active]:after:h-0.5 data-[status=active]:after:rounded-[2px] data-[status=active]:after:bg-primary data-[status=active]:after:content-['']";

export function SettingsTabs() {
  return (
    <nav aria-label="Settings sections" className="mb-4 flex flex-wrap gap-0.5 border-b">
      {SETTINGS_SECTIONS.map((section) => (
        <Link key={section} to="/settings/$section" params={{ section }} className={TAB}>
          {SECTION_LABELS[section]}
        </Link>
      ))}
    </nav>
  );
}

import { Code as CodeIcon } from 'lucide-react';

import { DashboardCard } from '@/components/DashboardCard';
import { ComingSoonTag } from '@/components/ComingSoon';
import { PlugIcon } from '@/components/icons';

import { Code, SettingsLead, SettingsRow } from './rows';

// The tag at the right of a card's title (.cs-tag.st-soon): smaller, flat.
const SOON = <ComingSoonTag className="px-[11px] py-[5px] text-[11px]/[normal]" />;

// API keys and the MCP server, both still to come. The public API works without a key: its docs
// are on this host, so stage links to stage, and so is the server's address.
export function ApiSection() {
  return (
    <>
      <DashboardCard icon={CodeIcon} title="API keys" aside={SOON}>
        <SettingsLead>
          Run backtests and read results from your own scripts. A key acts as you, so you keep it secret.
        </SettingsLead>
        <SettingsRow label="Public API" hint="Instruments and candles, no key needed">
          <a
            href="/api/v1/docs"
            target="_blank"
            rel="noopener"
            className="inline-block text-[13px]/[normal] font-medium text-primary underline hover:underline-offset-2"
          >
            API docs
          </a>
        </SettingsRow>
      </DashboardCard>
      <DashboardCard icon={PlugIcon} title="MCP server" aside={SOON}>
        <SettingsLead>
          Use CandleStack from Claude or ChatGPT. Ask about your backtests, start new ones and compare them in a chat.
          You sign in with your CandleStack account.
        </SettingsLead>
        <SettingsRow label="Server URL">
          <Code>{`${window.location.origin}/mcp`}</Code>
        </SettingsRow>
      </DashboardCard>
    </>
  );
}

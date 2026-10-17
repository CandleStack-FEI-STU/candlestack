import { Eyebrow } from '@/components/Eyebrow';

import { formatUsage } from './format';
import { useModels } from './useModels';

// The storage the models take, at the sidebar's foot (mockups/app, .dd-sfoot): a 6 px meter and
// the megabytes under it. Only once the API has said; no numbers to stand in meanwhile.
export function SidebarStorage() {
  const usage = useModels().data?.usage;
  if (!usage) return null;
  const share = usage.quota_bytes > 0 ? Math.min(1, usage.used_bytes / usage.quota_bytes) : 0;
  const text = `${formatUsage(usage.used_bytes, usage.quota_bytes)} models`;
  return (
    <>
      <Eyebrow>Storage</Eyebrow>
      {/* The line under it says the same in numbers. */}
      <span
        aria-hidden="true"
        className="block h-1.5 overflow-hidden rounded-sm bg-[color-mix(in_srgb,var(--ink)_9%,var(--bg))]"
      >
        <span className="block h-full bg-primary" style={{ width: `${share * 100}%` }} />
      </span>
      <span className="font-mono text-xs/normal">{text}</span>
    </>
  );
}

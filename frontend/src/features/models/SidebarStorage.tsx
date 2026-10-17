import { Eyebrow } from '@/components/Eyebrow';

import { formatUsage } from './format';
import { StorageMeter } from './StorageMeter';
import { useModels } from './useModels';

// The storage the models take, at the sidebar's foot (mockups/app, .dd-sfoot): a 6 px meter and
// the megabytes under it. Only once the API has said; no numbers to stand in meanwhile.
export function SidebarStorage() {
  const usage = useModels().data?.usage;
  if (!usage) return null;
  return (
    <>
      <Eyebrow>Storage</Eyebrow>
      <StorageMeter usage={usage} />
      <span className="font-mono text-xs/normal">{formatUsage(usage.used_bytes, usage.quota_bytes)} models</span>
    </>
  );
}

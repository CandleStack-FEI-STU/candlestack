import type { StorageUsage } from '@/api';

// The share of the storage the models take (.meter at 6 px): the accent on a darker surface. The
// numbers beside it say the same, so screen readers skip it.
export function StorageMeter({ usage }: { usage: StorageUsage }) {
  const share = usage.quota_bytes > 0 ? Math.min(1, usage.used_bytes / usage.quota_bytes) : 0;
  return (
    <span aria-hidden="true" className="block h-1.5 overflow-hidden rounded-sm bg-surface-2">
      <span className="block h-full bg-primary" style={{ width: `${share * 100}%` }} />
    </span>
  );
}

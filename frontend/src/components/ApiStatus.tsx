import { useHealth, type Health } from '@/api';
import { cn } from '@/lib/utils';

type HealthState = ReturnType<typeof useHealth>;

function describe({ data, error, isPending }: HealthState): string {
  if (isPending) return 'Checking the API…';
  if (error) return `API error: ${error.message}`;
  return describeReport(data);
}

function describeReport(health: Health | undefined): string {
  if (health?.status === 'ok') return `API ${health.version} (${health.env}) is up`;
  return `API ${health?.version ?? ''} has a problem (Redis ${health?.redis ?? 'unknown'})`;
}

function dotColor({ data, isPending }: HealthState): string {
  if (isPending) return 'bg-muted-foreground/50';
  return data?.status === 'ok' ? 'bg-primary' : 'bg-destructive';
}

// A small dot in the header: is the API there? Hover shows which version answers.
export function ApiStatus() {
  const health = useHealth();
  const label = describe(health);

  return (
    <output title={label} aria-label={label} className="flex items-center gap-2 text-xs text-muted-foreground">
      <span className={cn('size-2 rounded-full', dotColor(health))} />
      <span className="hidden font-mono sm:inline">{health.data ? `API ${health.data.version}` : 'API'}</span>
    </output>
  );
}

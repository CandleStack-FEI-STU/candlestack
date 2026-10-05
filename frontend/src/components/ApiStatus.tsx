import { useHealth } from '@/api'
import { cn } from '@/lib/utils'

// A small dot in the header: is the API there? Hover shows which version answers.
export function ApiStatus() {
  const { data, error, isPending } = useHealth()

  const ok = data?.status === 'ok'
  const label = isPending
    ? 'Checking the API…'
    : error
      ? `API error: ${error.message}`
      : ok
        ? `API ${data.version} (${data.env}) is up`
        : `API ${data?.version ?? ''} has a problem (Redis ${data?.redis ?? 'unknown'})`

  return (
    <span
      role="status"
      title={label}
      aria-label={label}
      className="flex items-center gap-2 text-xs text-muted-foreground"
    >
      <span
        className={cn(
          'size-2 rounded-full',
          isPending ? 'bg-muted-foreground/50' : ok ? 'bg-primary' : 'bg-destructive',
        )}
      />
      <span className="hidden font-mono sm:inline">{data ? `API ${data.version}` : 'API'}</span>
    </span>
  )
}

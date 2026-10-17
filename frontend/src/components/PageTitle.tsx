import { cn } from '@/lib/utils';

// The public pages leave 32 px under the title; the signed-in pages (mockups/app, .ttl) 20 px,
// with the line under the title 4 px closer.
const VARIANTS = {
  public: { row: 'mb-8', description: 'mt-2' },
  workspace: { row: 'mb-5', description: 'mt-1' },
};

type Props = { title: string; description?: string; variant?: keyof typeof VARIANTS };

// A page's title row: 30/36 semibold, a muted line under it.
export function PageTitle({ title, description, variant = 'public' }: Props) {
  const spacing = VARIANTS[variant];
  return (
    <div className={spacing.row}>
      <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
      {/* break-words: an error's description can hold a long path or id. */}
      {description && <p className={cn(spacing.description, 'break-words text-muted-foreground')}>{description}</p>}
    </div>
  );
}

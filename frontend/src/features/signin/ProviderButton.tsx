import type { ComponentType } from 'react';

import type { Provider } from '@/api';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

import { GitHubMark, GoogleMark } from './ProviderMarks';

// GitHub in ink, Google bordered on the background (it also takes the surface on hover).
const PROVIDERS: Record<Provider, { name: string; Mark: ComponentType<{ className?: string }>; look: string }> = {
  github: { name: 'GitHub', Mark: GitHubMark, look: 'border-foreground bg-foreground text-background' },
  google: {
    name: 'Google',
    Mark: GoogleMark,
    look: 'border-border bg-background text-foreground enabled:hover:bg-muted',
  },
};

type Props = { provider: Provider; busy: Provider | null; onStart: (provider: Provider) => void };

// "Continue with GitHub" (mockups/home, #/signin): 44 px high across the card, lifting 1 px with a
// shadow on hover. Once one is clicked both are disabled and dimmed, and the clicked one stays
// solid, saying "Opening GitHub" while the provider loads, its mark hidden behind the design's
// spinner: a 16 px ring in the text color, open on the right, turning every 0.7 s.
export function ProviderButton({ provider, busy, onStart }: Props) {
  const { name, Mark, look } = PROVIDERS[provider];
  const isBusy = busy === provider;
  return (
    <Button
      type="button"
      variant={null}
      size={null}
      disabled={busy !== null}
      onClick={() => onStart(provider)}
      className={cn(
        'relative h-11 w-full gap-2.5 rounded-lg border text-[15px]/[normal] transition-[translate,box-shadow,background-color,opacity] duration-150 enabled:hover:-translate-y-px enabled:hover:shadow-[0_6px_16px_var(--shadow)] disabled:opacity-55 motion-reduce:transition-none',
        look,
        isBusy && 'disabled:opacity-100',
      )}
    >
      {isBusy && (
        <span
          aria-hidden="true"
          className="absolute left-[calc(50%-82px)] size-4 animate-[spin_0.7s_linear_infinite] rounded-full border-2 border-current border-r-transparent motion-reduce:animate-none"
        />
      )}
      <Mark className={cn('size-[18px]', isBusy && 'invisible')} />
      <span>{isBusy ? `Opening ${name}` : `Continue with ${name}`}</span>
    </Button>
  );
}

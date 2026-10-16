import type { Me } from '@/api';
import { cn } from '@/lib/utils';

import { initials } from './initials';

// The user's drawn initials in a 30 px accent circle (mockups/app, .avatar). Decorative: the
// button around it says what it is.
export function Avatar({ user, className }: { user: Pick<Me, 'display_name' | 'email'>; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        'grid size-[30px] place-items-center rounded-full bg-[color-mix(in_srgb,var(--accent)_12%,var(--bg))] font-mono text-xs/[normal] font-semibold text-primary',
        className,
      )}
    >
      {initials(user.display_name, user.email)}
    </span>
  );
}

import type { ReactNode } from 'react';

import { LogoMark } from '@/brand/LogoMark';
import { AccentDot } from '@/components/AccentDot';
import { BUTTON_SIZES, GHOST_BUTTON, OUTLINE_BUTTON } from '@/components/buttonStyles';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

import { ProviderButton } from './ProviderButton';
import { PROVIDERS } from './providers';
import { useProviderSignIn } from './useProviderSignIn';

const TITLE = 'text-[22px]/7 font-semibold tracking-[-0.02em]';
const LEAD = 'mt-1.5 text-muted-foreground';

// The one card in the middle of the grid (mockups/home, #/signin): 400 px at most, the logo's
// tile over its content. It rises 8 px into place as it fades in.
export function SignInCard({ children }: { children: ReactNode }) {
  return (
    <div className="flex w-[min(400px,100%)] animate-in flex-col items-center gap-[18px] rounded-xl border bg-background px-7 pt-8 pb-[26px] text-center shadow-[0_10px_30px_var(--shadow)] duration-220 ease-out fade-in slide-in-from-bottom-2 motion-reduce:animate-none">
      <LogoMark className="size-11" />
      {children}
    </div>
  );
}

// The start: one page for signing in and signing up, as the first sign-in creates the account.
export function StartSignIn({ next }: { next: string | undefined }) {
  const { busy, start } = useProviderSignIn(next);
  return (
    <div>
      <h1 className={TITLE}>Sign in to CandleStack</h1>
      <p className={LEAD}>New here? The same buttons create your account.</p>
      <div className="mt-[22px] flex w-full flex-col gap-2.5">
        {PROVIDERS.map((provider) => (
          <ProviderButton key={provider} provider={provider} busy={busy} onStart={start} />
        ))}
      </div>
      <p className="mt-[18px] flex items-center justify-center gap-2 text-[12.5px] text-muted-foreground">
        <AccentDot />
        In beta, open to people on the beta list
      </p>
    </div>
  );
}

type DeniedProps = { email: string; onUseAnotherAccount: () => void };

// The provider knew the account, the beta list did not: who it was, and the two ways on.
export function DeniedSignIn({ email, onUseAnotherAccount }: DeniedProps) {
  return (
    <div>
      <h1 className={TITLE}>You are not on the beta list yet</h1>
      <p className={LEAD}>
        <b>{email}</b> cannot sign in during the beta. Ask the team for an invite, then try again.
      </p>
      <div className="mt-[22px] flex w-full justify-center gap-2.5">
        <Button
          type="button"
          variant="outline"
          className={cn(BUTTON_SIZES.default, OUTLINE_BUTTON)}
          onClick={onUseAnotherAccount}
        >
          Use another account
        </Button>
        <Button asChild variant="ghost" className={cn(BUTTON_SIZES.default, GHOST_BUTTON)}>
          <a href="https://candlestack.tech" target="_blank" rel="noopener">
            Contact the team
          </a>
        </Button>
      </div>
    </div>
  );
}

// Under the card: what signing in shares.
export function SignInLegal() {
  return (
    <p className="max-w-[400px] text-center text-xs/[1.5] text-muted-foreground">
      We only get your name and email. No password is stored.
    </p>
  );
}

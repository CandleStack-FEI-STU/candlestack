import { useQuery } from '@tanstack/react-query';
import { useNavigate, useSearch } from '@tanstack/react-router';

import { deniedSignInQueryOptions } from '@/api';
import { DeniedSignIn, SignInCard, SignInLegal, StartSignIn } from '@/features/signin';
import { usePageTitle } from '@/lib/usePageTitle';

// /signin?next=/backtests&error=denied, for Sign in and Try Backtest alike (mockups/home,
// #/signin). After a denied sign-in it names the account the beta list turned away (the route
// has loaded it); without that answer, and after a failed one, it simply offers the buttons.
export function SignInPage() {
  usePageTitle('Sign in');
  const { next, error } = useSearch({ from: '/_public/signin' });
  const navigate = useNavigate({ from: '/signin' });
  const denied = useQuery({ ...deniedSignInQueryOptions(), enabled: error === 'denied' });
  const email = error === 'denied' ? denied.data?.email : undefined;

  return (
    <section
      aria-label="Sign in"
      className="flex flex-1 flex-col items-center justify-center gap-4 py-12 text-sm/[1.5]"
    >
      <SignInCard>
        {email === undefined ? (
          <StartSignIn next={next} />
        ) : (
          <DeniedSignIn email={email} onUseAnotherAccount={() => void navigate({ search: { next }, replace: true })} />
        )}
      </SignInCard>
      <SignInLegal />
    </section>
  );
}

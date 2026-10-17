import { useEffect, useState } from 'react';

import { signInUrl, type Provider } from '@/api';

// Signing in with a provider: the page marks its button busy and leaves for the API, which sends
// the browser on to the provider. `next` is where the app opens afterwards.
export function useProviderSignIn(next: string | undefined) {
  const [busy, setBusy] = useState<Provider | null>(null);

  // Back from the provider's page, the browser may restore this page as it was left, still busy:
  // offer the buttons again.
  useEffect(() => {
    const onPageShow = (event: PageTransitionEvent) => {
      if (event.persisted) setBusy(null);
    };
    window.addEventListener('pageshow', onPageShow);
    return () => window.removeEventListener('pageshow', onPageShow);
  }, []);

  const start = (provider: Provider) => {
    setBusy(provider);
    window.location.assign(signInUrl(provider, next));
  };

  return { busy, start };
}

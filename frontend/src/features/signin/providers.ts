import type { ComponentType } from 'react';

import type { Provider } from '@/api';

import { GitHubMark, GoogleMark } from './ProviderMarks';

// The ways to sign in, in the order the design lists them, each with its name and mark: the
// sign-in page's buttons and the methods in Settings, Sign-in.
export const PROVIDERS: readonly Provider[] = ['github', 'google'];

export const PROVIDER_INFO: Record<Provider, { name: string; Mark: ComponentType<{ className?: string }> }> = {
  github: { name: 'GitHub', Mark: GitHubMark },
  google: { name: 'Google', Mark: GoogleMark },
};

import type { Theme } from '@/api';
import { useMe } from '@/features/account';
import { applyTheme, useTheme } from '@/theme';

import { useUpdateAppearance } from './useUpdateAppearance';

// The theme on the page and the way to change it, for the header's toggle and Settings: on the
// page at once, and signed in also on the account, so every device shows it.
export function useThemeSetting() {
  const theme = useTheme();
  const signedIn = Boolean(useMe());
  const { mutate } = useUpdateAppearance();
  const setTheme = (next: Theme) => {
    applyTheme(next);
    if (signedIn) mutate({ theme: next });
  };
  return { theme, setTheme };
}

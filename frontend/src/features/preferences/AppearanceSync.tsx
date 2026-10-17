import { useEffect } from 'react';

import { useMe } from '@/features/account';
import { applyReduceMotion } from '@/motion';
import { applyTheme } from '@/theme';

import { useAccountAppearance } from './useAppearance';

// Puts the account's theme and Reduce motion on the page whenever they arrive or change (from
// Settings, the header's toggle or a failed change going back): signed in, the account's
// settings win over what this browser had. Signed out, Reduce motion is the system's alone; the
// theme stays as it was, the toggle's.
export function AppearanceSync() {
  const signedOut = useMe() === null;
  const appearance = useAccountAppearance();

  useEffect(() => {
    if (appearance === undefined) return;
    applyTheme(appearance.theme);
    applyReduceMotion(appearance.reduce_motion);
  }, [appearance]);

  useEffect(() => {
    if (signedOut) applyReduceMotion(false);
  }, [signedOut]);

  return null;
}

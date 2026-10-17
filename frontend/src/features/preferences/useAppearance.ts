import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import { preferencesQueryOptions, type Appearance } from '@/api';
import { useMe } from '@/features/account';
import { dateStyleOf, type DateStyle } from '@/lib/dates';

// The account's appearance settings while someone is signed in and the API has sent them;
// undefined otherwise.
export function useAccountAppearance(): Appearance | undefined {
  const signedIn = Boolean(useMe());
  return useQuery({
    ...preferencesQueryOptions(),
    enabled: signedIn,
    select: (preferences) => preferences.appearance,
  }).data;
}

// How dates and times are written for whoever looks: the account's choice, or the defaults (New
// York time, 12 Oct 2024, 16:05) for a visitor.
export function useDateStyle(): DateStyle {
  const appearance = useAccountAppearance();
  return useMemo(() => dateStyleOf(appearance), [appearance]);
}

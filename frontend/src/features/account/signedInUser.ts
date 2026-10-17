import { createContext, useContext } from 'react';

import type { Me } from '@/api';

// The user of the signed-in pages. Their layout provides it once its guard has made sure there
// is one, so the header and the pages below it never deal with a missing user.
export const SignedInUserContext = createContext<Me | null>(null);

export function useSignedInUser(): Me {
  const user = useContext(SignedInUserContext);
  if (user === null) throw new Error('useSignedInUser is only for the pages of the signed-in layout');
  return user;
}

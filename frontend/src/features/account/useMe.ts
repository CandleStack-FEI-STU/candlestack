import { useQuery } from '@tanstack/react-query';

import { meQueryOptions, type Me } from '@/api';

// The signed-in user, null when signed out, undefined until the API has answered (the root
// route asks before the first page shows) or when it could not answer.
export function useMe(): Me | null | undefined {
  return useQuery(meQueryOptions()).data;
}

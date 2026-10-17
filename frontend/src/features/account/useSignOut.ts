import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from '@tanstack/react-router';

import { meQueryOptions, signOut } from '@/api';

// Ends the session, forgets the user and goes to the home page. The user is forgotten first: the
// signed-in layout shows nothing without one, so no page of the app is left on screen meanwhile.
// When the API cannot end the session (no answer, a server error), the session is still open:
// the user stays signed in on the page, and Sign out in the menu tries again.
export function useSignOut() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: signOut,
    onSuccess: async () => {
      queryClient.setQueryData(meQueryOptions().queryKey, null);
      await navigate({ to: '/' });
    },
  });
}

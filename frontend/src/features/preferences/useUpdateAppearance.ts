import { useMutation, useMutationState, useQueryClient } from '@tanstack/react-query';

import { preferencesQueryOptions, updateAppearance, type Appearance, type Preferences } from '@/api';

const MUTATION_KEY = ['account', 'appearance'];

// Changes some appearance settings: at once on the page (the cache the page reads, which
// AppearanceSync puts on <html>), then on the account. The changes go out one after another, in
// the order they were made; the API's answer is taken only once none is left on the way, so a
// slower answer never undoes a newer choice. A failed change goes back to what was there.
export function useUpdateAppearance() {
  const queryClient = useQueryClient();
  const key = preferencesQueryOptions().queryKey;
  return useMutation({
    mutationKey: MUTATION_KEY,
    scope: { id: 'appearance' },
    mutationFn: (update: Partial<Appearance>) => updateAppearance(update),
    onMutate: async (update): Promise<{ before: Preferences | undefined }> => {
      await queryClient.cancelQueries({ queryKey: key });
      const before = queryClient.getQueryData(key);
      queryClient.setQueryData(
        key,
        (preferences) => preferences && { ...preferences, appearance: { ...preferences.appearance, ...update } },
      );
      return { before };
    },
    onError: (_error, _update, context) => {
      if (context?.before) queryClient.setQueryData(key, context.before);
    },
    onSuccess: (appearance) => {
      if (queryClient.isMutating({ mutationKey: MUTATION_KEY }) > 1) return;
      queryClient.setQueryData(key, (preferences) => preferences && { ...preferences, appearance });
    },
  });
}

// Why the latest change failed, wherever it was made (Settings or the header's toggle); null once
// a change went through.
export function useAppearanceError(): Error | null {
  const errors = useMutationState({
    filters: { mutationKey: MUTATION_KEY },
    select: (mutation) => mutation.state.error,
  });
  return errors.at(-1) ?? null;
}

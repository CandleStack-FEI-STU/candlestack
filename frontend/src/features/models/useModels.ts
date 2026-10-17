import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';

import { deleteModel, modelsQueryOptions, updateModel, uploadModel, type Model, type Models } from '@/api';

const KEY = modelsQueryOptions().queryKey;

// The user's models and their storage, shared by the page and the sidebar.
export function useModels() {
  return useQuery(modelsQueryOptions());
}

// Puts the API's answer into the one models entry at once, then asks again for the storage
// numbers the API counts itself, without waiting for that answer.
function change(queryClient: QueryClient, update: (data: Models) => Models) {
  queryClient.setQueryData(KEY, (data) => (data ? update(data) : data));
  void queryClient.invalidateQueries({ queryKey: KEY });
}

const replace = (data: Models, model: Model): Models => ({
  ...data,
  models: data.models.map((item) => (item.id === model.id ? model : item)),
});

// Uploads a file; the new model joins the end of the list (oldest first) and takes its size of
// the storage. Not a mutation: the dialog keeps the upload's own state and aborts it on close.
export function useUploadModel() {
  const queryClient = useQueryClient();
  return async (file: File, signal: AbortSignal): Promise<Model> => {
    const model = await uploadModel(file, signal);
    change(queryClient, (data) => ({
      models: [...data.models, model],
      usage: { ...data.usage, used_bytes: data.usage.used_bytes + model.size_bytes },
    }));
    return model;
  };
}

// Stars or unstars at once; the star goes back when the API refuses.
export function useStarModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (model: Model) => updateModel(model.id, { starred: !model.starred }),
    onMutate: async (model) => {
      await queryClient.cancelQueries({ queryKey: KEY });
      const before = queryClient.getQueryData(KEY);
      queryClient.setQueryData(KEY, (data) => data && replace(data, { ...model, starred: !model.starred }));
      return { before };
    },
    onError: (_error, _model, context) => queryClient.setQueryData(KEY, context?.before),
    onSettled: () => queryClient.invalidateQueries({ queryKey: KEY }),
  });
}

// Renames a model: `name` is the part before the extension, which stays.
export function useRenameModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => updateModel(id, { name }),
    onSuccess: (model) => change(queryClient, (data) => replace(data, model)),
  });
}

// Deletes a model, which frees its size of the storage.
export function useDeleteModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (model: Model) => deleteModel(model.id),
    onSuccess: (_answer, model) =>
      change(queryClient, (data) => ({
        models: data.models.filter((item) => item.id !== model.id),
        usage: { ...data.usage, used_bytes: Math.max(0, data.usage.used_bytes - model.size_bytes) },
      })),
  });
}

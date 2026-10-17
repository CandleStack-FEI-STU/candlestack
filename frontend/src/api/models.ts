import { queryOptions } from '@tanstack/react-query';

import { del, get, patch, postFile } from './client';
import type { components } from './schema';

export type Model = components['schemas']['ModelOut'];
export type Models = components['schemas']['ModelsOut'];
export type ModelUpdate = components['schemas']['ModelUpdate'];

// GET /api/v1/models: the user's models, oldest first, and the storage they take. Under
// ['account', ...] like the user, so signing out knows to forget them. The page and the sidebar
// share it; every change to the models updates this one entry.
export function modelsQueryOptions() {
  return queryOptions({
    queryKey: ['account', 'models'],
    queryFn: ({ signal }) => get<Models>('/v1/models', signal),
  });
}

// POST /api/v1/models?name=...: the file itself is the body. The API checks it before it keeps
// it; a failed check is an ApiError with the problem model-check-failed and `check` in its body.
export function uploadModel(file: File, signal?: AbortSignal): Promise<Model> {
  const query = new URLSearchParams({ name: file.name }).toString();
  return postFile<Model>(`/v1/models?${query}`, file, signal);
}

// PATCH /api/v1/models/{id}: renames (the name without its extension) or stars the model.
export function updateModel(id: string, update: ModelUpdate): Promise<Model> {
  return patch<Model>(`/v1/models/${encodeURIComponent(id)}`, update);
}

// DELETE /api/v1/models/{id}: the model and its file go, which frees its storage.
export function deleteModel(id: string): Promise<void> {
  return del(`/v1/models/${encodeURIComponent(id)}`);
}

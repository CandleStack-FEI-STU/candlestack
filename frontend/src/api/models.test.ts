import { QueryClient } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { model, modelsAnswer, problem, stubApi } from '@/test/api';

import { ApiError } from './client';
import { deleteModel, modelsQueryOptions, updateModel, uploadModel } from './models';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('modelsQueryOptions', () => {
  it('reads the models and the storage, under the account so signing out forgets them', async () => {
    stubApi(modelsAnswer([model()]));
    const options = modelsQueryOptions();
    expect(options.queryKey).toEqual(['account', 'models']);
    const data = await new QueryClient().fetchQuery(options);
    expect(data.models).toEqual([model()]);
    expect(data.usage.quota_bytes).toBe(100 * 1024 * 1024);
  });
});

describe('uploadModel', () => {
  it('posts the file as the raw body, its name in the query', async () => {
    const fetch = stubApi({ 'POST /api/v1/models?name=lstm+signals.keras': { status: 201, body: model() } });
    const file = new File(['weights'], 'lstm signals.keras');
    await expect(uploadModel(file)).resolves.toEqual(model());
    const init = fetch.mock.calls[0]?.[1];
    expect(init?.body).toBe(file);
    expect(init?.headers).toMatchObject({ 'Content-Type': 'application/octet-stream' });
  });

  it('passes a failed check on with its slug and its check', async () => {
    stubApi({
      'POST /api/v1/models?name=a.keras': problem(422, 'model-check-failed', 'No weights.', { check: 'weights' }),
    });
    const error: unknown = await uploadModel(new File([''], 'a.keras')).catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 422, problem: 'model-check-failed', body: { check: 'weights' } });
  });
});

describe('updateModel', () => {
  it('patches the name or the star', async () => {
    const fetch = stubApi({ 'PATCH /api/v1/models/mdl_7f3k2m9qx4': { status: 200, body: model({ starred: true }) } });
    await expect(updateModel('mdl_7f3k2m9qx4', { starred: true })).resolves.toMatchObject({ starred: true });
    expect(fetch.mock.calls[0]?.[1]?.body).toBe('{"starred":true}');
  });

  it('passes a taken name on as model-name-taken', async () => {
    stubApi({ 'PATCH /api/v1/models/mdl_7f3k2m9qx4': problem(409, 'model-name-taken', 'Taken.') });
    await expect(updateModel('mdl_7f3k2m9qx4', { name: 'lstm' })).rejects.toMatchObject({
      problem: 'model-name-taken',
    });
  });
});

describe('deleteModel', () => {
  it('deletes the model', async () => {
    const fetch = stubApi({ 'DELETE /api/v1/models/mdl_7f3k2m9qx4': { status: 204 } });
    await expect(deleteModel('mdl_7f3k2m9qx4')).resolves.toBeUndefined();
    expect(fetch).toHaveBeenCalledOnce();
  });
});

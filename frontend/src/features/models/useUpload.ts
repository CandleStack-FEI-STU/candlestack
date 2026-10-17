import { useEffect, useRef, useState } from 'react';

import { ApiError, type Model, type StorageUsage } from '@/api';

import { frameworkOfFile, type Framework } from './frameworks';
import { formatSize } from './format';
import { useModels, useUploadModel } from './useModels';

// Why the API did not keep a file: one of its checks failed (`opens`, `weights`), it is too
// large, the storage is full, another upload of the user's is still running (`busy`), the user
// has as many models as allowed (`count`), the upload took too long (`timeout`), or something
// else went wrong on the way.
type DetailKind = 'opens' | 'weights' | 'large' | 'busy' | 'count' | 'timeout' | 'other';
export type UploadFailure = { kind: DetailKind; detail: string } | { kind: 'storage'; used: number; quota: number };

// The limits of the API that a failure shows with its own title and the API's words.
const LIMITS: Record<string, DetailKind> = {
  'upload-in-progress': 'busy',
  'too-many-models': 'count',
  'upload-timeout': 'timeout',
};

// The upload dialog's steps: choose a file; a file of a format not taken yet; the checks
// running; the model kept; or the reason it was not.
export type UploadState =
  | { step: 'pick' }
  | { step: 'soon'; file: File; framework: Framework | null }
  | { step: 'checking'; file: File }
  | { step: 'ready'; file: File; model: Model }
  | { step: 'failed'; file: File; failure: UploadFailure };

const numberIn = (body: unknown, key: string): number | undefined => {
  const value = typeof body === 'object' && body !== null ? (body as Record<string, unknown>)[key] : undefined;
  return typeof value === 'number' ? value : undefined;
};

const checkOf = (body: unknown) => (typeof body === 'object' && body !== null && 'check' in body ? body.check : null);

function storageFailure(body: unknown, usage: StorageUsage | undefined): UploadFailure {
  return {
    kind: 'storage',
    used: numberIn(body, 'used_bytes') ?? usage?.used_bytes ?? 0,
    quota: numberIn(body, 'quota_bytes') ?? usage?.quota_bytes ?? 0,
  };
}

// `usage`: the storage as the app last heard it, for a storage-full answer without its numbers.
export function failureOf(error: unknown, usage?: StorageUsage): UploadFailure {
  if (!(error instanceof ApiError)) {
    return { kind: 'other', detail: error instanceof Error ? error.message : String(error) };
  }
  const detail = error.message;
  if (error.problem === 'model-check-failed') {
    return { kind: checkOf(error.body) === 'weights' ? 'weights' : 'opens', detail };
  }
  if (error.problem === 'model-too-large' || error.status === 413) return { kind: 'large', detail };
  if (error.problem === 'storage-full') {
    return storageFailure(error.body, usage);
  }
  return { kind: LIMITS[error.problem ?? ''] ?? 'other', detail };
}

const isUnsupported = (error: unknown) => error instanceof ApiError && error.problem === 'unsupported-model-format';

// The state of one upload at a time. A Keras file goes to the API at once; any other format
// stays here (no request). Closing the dialog unmounts its content, which aborts the upload.
export function useUpload() {
  const [state, setState] = useState<UploadState>({ step: 'pick' });
  const controller = useRef<AbortController | null>(null);
  const upload = useUploadModel();
  const usage = useModels().data?.usage;

  useEffect(() => () => controller.current?.abort(), []);

  const choose = (file: File) => {
    const framework = frameworkOfFile(file.name);
    if (framework !== 'Keras') {
      setState({ step: 'soon', file, framework });
      return;
    }
    // Too large for the API to take: said at once, without sending 50 MB first.
    if (usage && file.size > usage.file_max_bytes) {
      setState({ step: 'failed', file, failure: { kind: 'large', detail: `The file is ${formatSize(file.size)}.` } });
      return;
    }
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    setState({ step: 'checking', file });
    upload(file, current.signal).then(
      (model) => setState({ step: 'ready', file, model }),
      (error: unknown) => {
        if (current.signal.aborted) return;
        // The API knows the formats best: one it does not take yet is not a failed check.
        if (isUnsupported(error)) setState({ step: 'soon', file, framework: null });
        else setState({ step: 'failed', file, failure: failureOf(error, usage) });
      },
    );
  };

  const reset = () => setState({ step: 'pick' });

  return { state, choose, reset };
}

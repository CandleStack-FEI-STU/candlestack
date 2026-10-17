import { useEffect, useRef, useState } from 'react';

import { ApiError, type Model } from '@/api';

import { frameworkOfFile, type Framework } from './frameworks';
import { useUploadModel } from './useModels';

// Why the API did not keep a file: one of its checks failed (`opens`, `weights`), it is too
// large, the storage is full, or something else went wrong on the way.
export type UploadFailure =
  { kind: 'opens' | 'weights' | 'large' | 'other'; detail: string } | { kind: 'storage'; used: number; quota: number };

// The upload dialog's steps: choose a file; a file of a format not taken yet; the checks
// running; the model kept; or the reason it was not.
export type UploadState =
  | { step: 'pick' }
  | { step: 'soon'; file: File; framework: Framework | null }
  | { step: 'checking'; file: File }
  | { step: 'ready'; file: File; model: Model }
  | { step: 'failed'; file: File; failure: UploadFailure };

const numberIn = (body: unknown, key: string): number => {
  const value = typeof body === 'object' && body !== null ? (body as Record<string, unknown>)[key] : undefined;
  return typeof value === 'number' ? value : 0;
};

const checkOf = (body: unknown) => (typeof body === 'object' && body !== null && 'check' in body ? body.check : null);

export function failureOf(error: unknown): UploadFailure {
  if (!(error instanceof ApiError)) {
    return { kind: 'other', detail: error instanceof Error ? error.message : String(error) };
  }
  const detail = error.message;
  if (error.problem === 'model-check-failed') {
    return { kind: checkOf(error.body) === 'weights' ? 'weights' : 'opens', detail };
  }
  if (error.problem === 'model-too-large' || error.status === 413) return { kind: 'large', detail };
  if (error.problem === 'storage-full') {
    return { kind: 'storage', used: numberIn(error.body, 'used_bytes'), quota: numberIn(error.body, 'quota_bytes') };
  }
  return { kind: 'other', detail };
}

const isUnsupported = (error: unknown) => error instanceof ApiError && error.problem === 'unsupported-model-format';

// The state of one upload at a time. A Keras file goes to the API at once; any other format
// stays here (no request). Closing the dialog unmounts its content, which aborts the upload.
export function useUpload() {
  const [state, setState] = useState<UploadState>({ step: 'pick' });
  const controller = useRef<AbortController | null>(null);
  const upload = useUploadModel();

  useEffect(() => () => controller.current?.abort(), []);

  const choose = (file: File) => {
    const framework = frameworkOfFile(file.name);
    if (framework !== 'Keras') {
      setState({ step: 'soon', file, framework });
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
        else setState({ step: 'failed', file, failure: failureOf(error) });
      },
    );
  };

  const reset = () => setState({ step: 'pick' });

  return { state, choose, reset };
}

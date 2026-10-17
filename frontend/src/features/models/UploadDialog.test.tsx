// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  Outlet,
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from '@tanstack/react-router';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ARSEN, MB, model, modelsAnswer, problem, session, stubApi } from '@/test/api';
import { renderApp } from '@/test/app';

import { UploadDialog } from './UploadDialog';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const UPLOAD = 'POST /api/v1/models?name=lstm-signals.keras';
const LSTM = model({ id: 'mdl_a2b3c4d5e6', name: 'lstm-signals.keras', size_bytes: Math.round(12.4 * MB) });

// A file of `mb` megabytes; only its size and name matter.
function file(name: string, mb = 12.4) {
  const item = new File(['x'], name);
  Object.defineProperty(item, 'size', { value: Math.round(mb * MB) });
  return item;
}

type Answers = Parameters<typeof stubApi>[0];

// The dialog on another page than Models, as the dashboard will have it.
function renderElsewhere() {
  const root = createRootRoute({
    component: () => (
      <>
        <UploadDialog onBacktest={() => undefined}>
          <button type="button">Upload</button>
        </UploadDialog>
        <Outlet />
      </>
    ),
  });
  const page = (path: string) => createRoute({ getParentRoute: () => root, path });
  const router = createRouter({
    routeTree: root.addChildren([page('/dashboard'), page('/models')]),
    history: createMemoryHistory({ initialEntries: ['/dashboard'] }),
  });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

async function openUpload(answers: Answers = {}, url = '/models') {
  const fetch = stubApi({ ...session(ARSEN), ...modelsAnswer([]), ...answers });
  const app = await renderApp(url);
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: /^Upload model/ }));
  const dialog = within(screen.getByRole('dialog', { name: 'Upload model' }));
  const choose = (item: File) => fireEvent.change(dialog.getByLabelText('Model file'), { target: { files: [item] } });
  return { ...app, fetch, user, dialog, choose };
}

// The checks as screen readers hear them: their state, title and hint.
const checks = (dialog: { getAllByRole: (role: 'listitem') => HTMLElement[] }) =>
  dialog.getAllByRole('listitem').map((item) => item.textContent);

describe('the upload dialog', () => {
  it('opens on the drop zone, a file picker that offers every format', async () => {
    const { dialog } = await openUpload();
    const zone = dialog.getByRole('button', { name: /Drop a trained model here/ });
    expect([...zone.children].map((child) => child.textContent)).toEqual([
      '',
      'Drop a trained model here',
      'or click to choose a file. Up to 50 MB.',
      ['Keras', 'TensorFlow', 'PyTorch', 'ONNX', 'scikit-learn'].join(''),
    ]);
    const input = dialog.getByLabelText<HTMLInputElement>('Model file');
    expect([input.type, input.accept]).toEqual(['file', '.keras,.h5,.pb,.zip,.pt,.pth,.onnx,.joblib,.pkl,.skops']);
    expect(dialog.queryByRole('button', { name: 'Cancel' })).toBeNull();
  });

  it('keeps an empty live region in the accessibility tree for the first announcement', async () => {
    const { dialog } = await openUpload();
    const region = dialog.getByRole('button', { name: /Drop a trained model here/ }).nextElementSibling;
    expect(region?.getAttribute('aria-live')).toBe('polite');
    expect(region?.childElementCount).toBe(0);
  });

  it('opens the file picker on a click of the drop zone', async () => {
    const { user, dialog } = await openUpload();
    const input = dialog.getByLabelText<HTMLInputElement>('Model file');
    const click = vi.spyOn(input, 'click');
    await user.click(dialog.getByRole('button', { name: /Drop a trained model here/ }));
    expect(click).toHaveBeenCalledOnce();
  });

  it('marks the drop zone while a file is dragged over it and takes the file dropped', async () => {
    const { dialog, fetch } = await openUpload({ [UPLOAD]: { status: 201, body: LSTM } });
    const zone = dialog.getByRole('button', { name: /Drop a trained model here/ });
    fireEvent.dragEnter(zone);
    expect(zone.dataset.dragging).toBe('true');
    fireEvent.dragLeave(zone, { relatedTarget: document.body });
    expect(zone.dataset.dragging).toBeUndefined();
    fireEvent.dragOver(zone);
    fireEvent.drop(zone, { dataTransfer: { files: [file('lstm-signals.keras')] } });

    expect(await dialog.findByText('lstm-signals.keras is ready')).toBeDefined();
    expect(fetch).toHaveBeenCalledWith('/api/v1/models?name=lstm-signals.keras', expect.anything());
  });

  it('says another format is coming soon, without asking the API', async () => {
    const { dialog, fetch, choose } = await openUpload();
    const asked = fetch.mock.calls.length;
    choose(file('tcn-signals.pt', 8.1));

    expect(dialog.getByText('tcn-signals.pt')).toBeDefined();
    expect(dialog.getByText('PyTorch · 8.1 MB')).toBeDefined();
    expect(dialog.getByTitle('PyTorch')).toBeDefined();
    expect(checks(dialog)).toEqual([
      'Not yet: Support for this format is coming soonFor now CandleStack takes Keras models (.keras).',
    ]);
    expect(dialog.getByRole('button', { name: 'Cancel' })).toBeDefined();
    expect(dialog.getByRole('button', { name: 'Choose another file' })).toBeDefined();
    expect(fetch.mock.calls.length).toBe(asked);
  });

  it('shows a file of no known format by its name only', async () => {
    const { dialog, choose } = await openUpload();
    choose(file('notes.txt'));
    const row = dialog.getByText('notes.txt').closest('div');
    expect(row?.textContent).toBe('notes.txt');
    expect(row?.querySelector('[title]')).toBeNull();
    expect(checks(dialog)[0]).toContain('Support for this format is coming soon');
  });

  it('shows both checks pending in their place while the upload runs', async () => {
    const { dialog, choose } = await openUpload({ [UPLOAD]: () => new Promise(() => {}) });
    choose(file('lstm-signals.keras'));

    expect(dialog.getByText('Keras · 12.4 MB')).toBeDefined();
    expect(checks(dialog)).toEqual([
      'Checking: Opens as a Keras model, no custom code inside',
      'Checking: Trained weights inside',
    ]);
    expect(dialog.getByRole('button', { name: 'Cancel' })).toBeDefined();
    expect(dialog.queryByRole('button', { name: 'Done' })).toBeNull();
  });

  it('sends the file as the raw body, its name in the query', async () => {
    const { fetch, dialog, choose } = await openUpload({ [UPLOAD]: { status: 201, body: LSTM } });
    const chosen = file('lstm-signals.keras');
    choose(chosen);
    await dialog.findByText('lstm-signals.keras is ready');
    const init = fetch.mock.calls.find(([, options]) => options?.method === 'POST')?.[1];
    expect(init?.body).toBe(chosen);
    expect(init?.headers).toMatchObject({ 'Content-Type': 'application/octet-stream' });
  });

  it('passes both checks: the model is ready and joins the page', async () => {
    const kept = model({ ...LSTM, name: 'lstm-signals (2).keras', parameters: 1_240_000, input_shape: [25, 101] });
    const { dialog, choose, user } = await openUpload({
      [UPLOAD]: { status: 201, body: kept },
    });
    stubApi({ ...modelsAnswer([kept]), [UPLOAD]: { status: 201, body: kept } });
    choose(file('lstm-signals.keras'));

    expect(await dialog.findByText('lstm-signals (2).keras is ready')).toBeDefined();
    expect(checks(dialog)).toEqual([
      'Passed: Opens as a Keras model, no custom code inside',
      'Passed: Trained weights inside1.24 M parameters',
    ]);
    expect(dialog.getByText('Keras · 1.24 M parameters · in 25 × 101 → 1')).toBeDefined();
    expect(screen.getByText('1 model · 12.4 MB of 100 MB used')).toBeDefined();
    // The page behind the dialog is hidden from screen readers while it is open.
    expect(screen.getAllByRole('article', { hidden: true })).toHaveLength(1);

    await user.click(dialog.getByRole('button', { name: 'Done' }));
    await vi.waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });

  it('leaves the shape out of the summary when the file does not say it', async () => {
    const kept = model({ ...LSTM, parameters: 9_325, input_shape: null, output_shape: null });
    const { dialog, choose } = await openUpload({ [UPLOAD]: { status: 201, body: kept } });
    choose(file('lstm-signals.keras'));
    expect(await dialog.findByText('Keras · 9,325 parameters')).toBeDefined();
    expect(checks(dialog)[1]).toBe('Passed: Trained weights inside9,325 parameters');
  });

  it('goes to the Models page on Done when it was opened elsewhere', async () => {
    stubApi({ ...modelsAnswer([]), [UPLOAD]: { status: 201, body: LSTM } });
    const router = renderElsewhere();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Upload' }));
    const dialog = within(screen.getByRole('dialog', { name: 'Upload model' }));
    fireEvent.change(dialog.getByLabelText('Model file'), { target: { files: [file('lstm-signals.keras')] } });
    await dialog.findByText('lstm-signals.keras is ready');
    await user.click(dialog.getByRole('button', { name: 'Done' }));
    await vi.waitFor(() => expect(router.state.location.pathname).toBe('/models'));
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('opens New backtest from Backtest with it', async () => {
    const { dialog, choose, user } = await openUpload({ [UPLOAD]: { status: 201, body: LSTM } });
    choose(file('lstm-signals.keras'));
    await dialog.findByText('lstm-signals.keras is ready');
    await user.click(dialog.getByRole('button', { name: 'Backtest with it' }));

    const next = await screen.findByRole('dialog', { name: 'New backtest' });
    expect(next.textContent).toContain('Coming soon');
    expect(screen.queryByRole('dialog', { name: 'Upload model' })).toBeNull();
  });

  // Once the file is in, the API checks and keeps it whatever the page does: closing the dialog
  // lets the upload come to its answer, and a model the API kept joins the page.
  it('shows the model the API kept after the dialog closed during its checks', async () => {
    let answer = (_value: { status: number; body: unknown }) => undefined as void;
    let request: RequestInit | undefined;
    const { dialog, choose, user } = await openUpload({
      [UPLOAD]: (init) => {
        request = init;
        return new Promise((resolve) => {
          answer = resolve;
        });
      },
    });
    choose(file('lstm-signals.keras'));
    await vi.waitFor(() => expect(request).toBeDefined());
    await user.click(dialog.getByRole('button', { name: 'Cancel' }));
    await vi.waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(request?.signal?.aborted ?? false).toBe(false);
    expect(screen.getByText('0 models · 0 MB of 100 MB used')).toBeDefined();

    stubApi(modelsAnswer([LSTM]));
    answer({ status: 201, body: LSTM });
    expect(await screen.findByText('1 model · 12.4 MB of 100 MB used')).toBeDefined();
    expect(screen.getAllByRole('article')).toHaveLength(1);
  });

  it('asks for the models again when an upload ends without the model: the API may have kept it', async () => {
    let fail = () => undefined as void;
    const { fetch, dialog, choose, user } = await openUpload({
      [UPLOAD]: () =>
        new Promise((_resolve, reject) => {
          fail = () => reject(new TypeError('Failed to fetch'));
        }),
    });
    choose(file('lstm-signals.keras'));
    await user.click(dialog.getByRole('button', { name: 'Cancel' }));
    const listed = () => fetch.mock.calls.filter(([path]) => path === '/api/v1/models').length;
    const before = listed();
    fail();
    await vi.waitFor(() => expect(listed()).toBe(before + 1));
  });

  it('says a file over the limit is too large without sending it', async () => {
    const { fetch, dialog, choose } = await openUpload();
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/v1/models', expect.anything()));
    choose(file('lstm-signals.keras', 61.2));
    expect(checks(dialog)).toEqual(['Failed: Larger than 50 MBThe file is 61.2 MB.']);
    expect(fetch.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
    expect(dialog.getByRole('button', { name: 'Choose another file' })).toBeDefined();
  });
});

describe('a failed upload', () => {
  async function failWith(answer: Answers[string]) {
    const opened = await openUpload({ [UPLOAD]: answer });
    opened.choose(file('lstm-signals.keras'));
    await vi.waitFor(() => expect(opened.dialog.getByRole('button', { name: 'Choose another file' })).toBeDefined());
    return opened;
  }

  it('without trained weights: the first check passed, the second did not', async () => {
    const { dialog } = await failWith(problem(422, 'model-check-failed', 'No weights.', { check: 'weights' }));
    expect(checks(dialog)).toEqual([
      'Passed: Opens as a Keras model, no custom code inside',
      'Failed: No trained weights in the fileIt holds the layers only. Save the model after training and upload that file.',
    ]);
    expect(dialog.getByRole('button', { name: 'Cancel' })).toBeDefined();
  });

  it('that does not open: why, in the words of the API, and no second check', async () => {
    const { dialog } = await failWith(
      problem(422, 'model-check-failed', 'The file holds custom code (a Lambda layer).', { check: 'opens' }),
    );
    expect(checks(dialog)).toEqual([
      'Failed: Does not open as a safe Keras modelThe file holds custom code (a Lambda layer).',
    ]);
  });

  it('too large', async () => {
    const { dialog } = await failWith(problem(413, 'model-too-large', 'The file is 61.2 MB; the limit is 50 MB.'));
    expect(checks(dialog)).toEqual(['Failed: Larger than 50 MBThe file is 61.2 MB; the limit is 50 MB.']);
  });

  it('with the storage full: what is used of it', async () => {
    const { dialog } = await failWith(
      problem(409, 'storage-full', 'Full.', { used_bytes: Math.round(92.3 * MB), quota_bytes: 100 * MB }),
    );
    expect(checks(dialog)).toEqual(['Failed: Not enough storage92.3 MB of 100 MB used. Delete a model to free space.']);
  });

  it('with the storage full and no numbers in the answer: the numbers the app has', async () => {
    const { dialog, choose } = await openUpload({
      ...modelsAnswer([model({ size_bytes: 92 * MB })]),
      [UPLOAD]: problem(409, 'storage-full', 'Full.'),
    });
    await dialog.findByRole('button', { name: /Drop a trained model here/ });
    await vi.waitFor(() => expect(screen.getByText('1 model · 92 MB of 100 MB used')).toBeDefined());
    choose(file('lstm-signals.keras'));
    await vi.waitFor(() =>
      expect(checks(dialog)).toEqual(['Failed: Not enough storage92 MB of 100 MB used. Delete a model to free space.']),
    );
  });

  it('while another upload is in progress: why, in the words of the API', async () => {
    const { dialog } = await failWith(
      problem(409, 'upload-in-progress', 'Another upload of yours is still in progress. Wait for it to finish.'),
    );
    expect(checks(dialog)).toEqual([
      'Failed: Another upload is in progressAnother upload of yours is still in progress. Wait for it to finish.',
    ]);
    expect(dialog.getByRole('button', { name: 'Cancel' })).toBeDefined();
  });

  it('with as many models as allowed: why, in the words of the API', async () => {
    const { dialog } = await failWith(
      problem(409, 'too-many-models', 'You have 100 models, the most you can keep. Delete one first.', { limit: 100 }),
    );
    expect(checks(dialog)).toEqual([
      'Failed: Too many modelsYou have 100 models, the most you can keep. Delete one first.',
    ]);
  });

  it('that took too long: why, in the words of the API', async () => {
    const { dialog } = await failWith(problem(408, 'upload-timeout', 'The file did not arrive in time. Try again.'));
    expect(checks(dialog)).toEqual(['Failed: Upload timed outThe file did not arrive in time. Try again.']);
  });

  it('for any other reason: the message', async () => {
    const { dialog } = await failWith({ status: 500, body: { detail: 'Something broke on our side.' } });
    expect(checks(dialog)).toEqual(['Failed: Upload failedSomething broke on our side.']);
  });

  it("refused by the API's check of the request: plain words, not the API's", async () => {
    const { dialog } = await failWith(
      problem(422, 'validation', "query parameter 'name': String should have at most 255 characters"),
    );
    expect(checks(dialog)).toEqual(['Failed: Upload failedThe file could not be sent. Rename it and try again.']);
  });

  it('without an answer: the message', async () => {
    const { dialog } = await failWith(() => Promise.reject(new TypeError('Failed to fetch')));
    expect(checks(dialog)).toEqual(['Failed: Upload failedCannot reach the server. Check your connection.']);
  });

  it('of a format the API does not take: coming soon', async () => {
    const { dialog } = await failWith(problem(415, 'unsupported-model-format', 'Keras only.'));
    expect(checks(dialog)[0]).toContain('Support for this format is coming soon');
  });

  it('offers another file: back to the drop zone, with the file picker open', async () => {
    const { dialog, user } = await failWith(problem(413, 'model-too-large', 'Too large.'));
    const click = vi.spyOn(dialog.getByLabelText<HTMLInputElement>('Model file'), 'click');
    await user.click(dialog.getByRole('button', { name: 'Choose another file' }));
    expect(dialog.getByRole('button', { name: /Drop a trained model here/ })).toBeDefined();
    expect(click).toHaveBeenCalledOnce();
  });
});

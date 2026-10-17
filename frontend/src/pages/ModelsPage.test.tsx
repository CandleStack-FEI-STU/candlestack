// @vitest-environment jsdom
import { cleanup, screen, within } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { modelsQueryOptions } from '@/api';
import {
  ARSEN,
  DEFAULT_PREFERENCES,
  MB,
  model,
  modelsAnswer,
  problem,
  session,
  sessionWithPreferences,
  stubApi,
} from '@/test/api';
import { renderApp } from '@/test/app';

const TSMIXER = model();
const LSTM = model({
  id: 'mdl_a2b3c4d5e6',
  name: 'lstm-signals.keras',
  size_bytes: 3 * MB,
  parameters: 9_325,
  input_shape: [25, 101],
  output_shape: null,
  starred: true,
  backtest_count: 1,
  best_sharpe: -0.184,
  created_at: '2026-10-17T08:00:00Z',
});
const DRAFT = model({
  id: 'mdl_q7r8s9t2u3',
  name: 'draft.keras',
  input_shape: null,
  backtest_count: 3,
  best_sharpe: 1.344,
});

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-10-17T12:00:00Z'));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const tiles = () => screen.getAllByRole('article');
const tile = (name: string) => within(tiles().find((item) => item.textContent?.includes(name)) ?? document.body);
const subtitle = () => screen.getByRole('heading', { level: 1 }).parentElement?.querySelector('p')?.textContent;

describe('the Models page', () => {
  it('says how many models there are and the storage they take, the Upload card beside it', async () => {
    stubApi({ ...session(ARSEN), ...modelsAnswer([TSMIXER, LSTM]) });
    await renderApp('/models');
    expect(await screen.findByText('2 models · 17.2 MB of 100 MB used')).toBeDefined();
    expect(screen.getByRole('button', { name: /^Upload model/ })).toBeDefined();
    expect(document.title).toBe('Models · CandleStack');
  });

  it('says model for one, and shows no tiles without models', async () => {
    stubApi({ ...session(ARSEN), ...modelsAnswer([LSTM]) });
    await renderApp('/models');
    expect(await screen.findByText('1 model · 3 MB of 100 MB used')).toBeDefined();
    cleanup();

    stubApi({ ...session(ARSEN), ...modelsAnswer([]) });
    await renderApp('/models');
    expect(await screen.findByText('0 models · 0 MB of 100 MB used')).toBeDefined();
    expect(screen.queryAllByRole('article')).toEqual([]);
  });

  it('says why the models could not load', async () => {
    stubApi({ ...session(ARSEN), 'GET /api/v1/models': { status: 503, body: { detail: 'Down for a minute.' } } });
    await renderApp('/models');
    expect(await screen.findByText('Down for a minute.')).toBeDefined();
    expect(subtitle()).toBe('Down for a minute.');
  });

  it('shows a tile per model in the order of the API', async () => {
    stubApi({ ...session(ARSEN), ...modelsAnswer([TSMIXER, LSTM, DRAFT]) });
    await renderApp('/models');
    await screen.findByText('3 models · 31.4 MB of 100 MB used');
    expect(tiles().map((item) => item.querySelector('b')?.textContent)).toEqual([
      'my-tsmixer.keras',
      'lstm-signals.keras',
      'draft.keras',
    ]);
  });

  it('writes what a model is, the shape it reads and its results', async () => {
    stubApi({ ...session(ARSEN), ...modelsAnswer([TSMIXER, LSTM, DRAFT]) });
    await renderApp('/models');
    await screen.findByText('3 models · 31.4 MB of 100 MB used');

    const tsmixer = tile('my-tsmixer.keras');
    expect(tsmixer.getByTitle('Keras')).toBeDefined();
    expect(tsmixer.getByTitle('my-tsmixer.keras').textContent).toBe('my-tsmixer.keras');
    expect(tsmixer.getByText('Keras · 14.2 MB · added 13 Oct')).toBeDefined();
    expect(tsmixer.getByText('in 25×23 → 1')).toBeDefined();
    expect(tsmixer.getByText('–').nextElementSibling?.textContent).toBe('best Sharpe');
    expect(tsmixer.getByText('0').nextElementSibling?.textContent).toBe('backtests');

    const lstm = tile('lstm-signals.keras');
    expect(lstm.getByText('Keras · 3.0 MB · added Today')).toBeDefined();
    expect(lstm.getByText('in 25×101')).toBeDefined();
    expect(lstm.getByText('−0.18')).toBeDefined();
    expect(lstm.getByText('1').nextElementSibling?.textContent).toBe('backtest');

    const draft = tile('draft.keras');
    expect(draft.getByText('Shape not in the file')).toBeDefined();
    expect(draft.getByText('1.34')).toBeDefined();
    expect(draft.getByText('3').nextElementSibling?.textContent).toBe('backtests');
  });

  it('writes the day a model was added in the date format and zone of the account', async () => {
    const appearance = { ...DEFAULT_PREFERENCES.appearance, date_format: 'iso', time_zone: 'local' } as const;
    stubApi({
      ...sessionWithPreferences(ARSEN, { ...DEFAULT_PREFERENCES, appearance }),
      ...modelsAnswer([TSMIXER, LSTM]),
    });
    await renderApp('/models');
    expect(await screen.findByText('Keras · 14.2 MB · added 2026-10-13')).toBeDefined();
    expect(tile('lstm-signals.keras').getByText('Keras · 3.0 MB · added Today')).toBeDefined();
  });

  it('stars a model at once, then keeps what the API answered', async () => {
    stubApi({ ...session(ARSEN), ...modelsAnswer([TSMIXER]) });
    const { queryClient } = await renderApp('/models');
    await screen.findByText('1 model · 14.2 MB of 100 MB used');
    const star = tile('my-tsmixer.keras').getByRole('button', { name: 'Star model my-tsmixer.keras' });
    expect([star.textContent, star.title, star.getAttribute('aria-pressed')]).toEqual(['☆', 'Star', 'false']);

    const starred = model({ starred: true });
    const fetch = stubApi({
      ...modelsAnswer([starred]),
      'PATCH /api/v1/models/mdl_7f3k2m9qx4': { status: 200, body: starred },
    });
    await userEvent.setup().click(star);
    expect([star.textContent, star.title, star.getAttribute('aria-pressed')]).toEqual(['★', 'Remove star', 'true']);
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/v1/models/mdl_7f3k2m9qx4', expect.anything()));
    expect(fetch.mock.calls.find(([path]) => path.endsWith('mdl_7f3k2m9qx4'))?.[1]?.body).toBe('{"starred":true}');
    await vi.waitFor(() =>
      expect(queryClient.getQueryData(modelsQueryOptions().queryKey)?.models[0]?.starred).toBe(true),
    );
  });

  it('shows the star before the API answers', async () => {
    stubApi({ ...session(ARSEN), ...modelsAnswer([TSMIXER]) });
    await renderApp('/models');
    await screen.findByText('1 model · 14.2 MB of 100 MB used');
    stubApi({ ...modelsAnswer([TSMIXER]), 'PATCH /api/v1/models/mdl_7f3k2m9qx4': () => new Promise(() => {}) });
    const star = tile('my-tsmixer.keras').getByRole('button', { name: 'Star model my-tsmixer.keras' });
    await userEvent.setup().click(star);
    expect(star.textContent).toBe('★');
  });

  it('puts the star back when the API refuses it', async () => {
    stubApi({ ...session(ARSEN), ...modelsAnswer([LSTM]) });
    await renderApp('/models');
    await screen.findByText('1 model · 3 MB of 100 MB used');
    const star = tile('lstm-signals.keras').getByRole('button', { name: 'Star model lstm-signals.keras' });
    expect(star.textContent).toBe('★');

    stubApi({
      ...modelsAnswer([LSTM]),
      'PATCH /api/v1/models/mdl_a2b3c4d5e6': { status: 503, body: { detail: 'Down.' } },
    });
    await userEvent.setup().click(star);
    await vi.waitFor(() => expect(star.textContent).toBe('★'));
  });
});

describe('Rename model', () => {
  async function openRename() {
    stubApi({ ...session(ARSEN), ...modelsAnswer([TSMIXER, LSTM]) });
    const rendered = await renderApp('/models');
    await screen.findByText('2 models · 17.2 MB of 100 MB used');
    const user = userEvent.setup();
    await user.click(tile('my-tsmixer.keras').getByRole('button', { name: 'Rename my-tsmixer.keras' }));
    const dialog = within(screen.getByRole('dialog', { name: 'Rename model' }));
    const input = dialog.getByRole<HTMLInputElement>('textbox', { name: 'Model name' });
    return { ...rendered, user, dialog, input, save: dialog.getByRole<HTMLButtonElement>('button', { name: 'Save' }) };
  }

  it('edits the name without its extension, focused and selected', async () => {
    const { dialog, input, save } = await openRename();
    expect(input.value).toBe('my-tsmixer');
    expect(input.maxLength).toBe(60);
    expect(document.activeElement).toBe(input);
    expect([input.selectionStart, input.selectionEnd]).toEqual([0, 'my-tsmixer'.length]);
    expect(dialog.getByText('Name')).toBeDefined();
    expect(dialog.getByText('.keras')).toBeDefined();
    expect(
      dialog.getByText('The extension stays .keras. Backtests that used this model show the new name.'),
    ).toBeDefined();
    expect(dialog.getByRole('button', { name: 'Cancel' })).toBeDefined();
    expect(save.disabled).toBe(true);
  });

  it('keeps Save off while the name is empty or unchanged', async () => {
    const { user, input, save } = await openRename();
    await user.clear(input);
    await user.type(input, '   ');
    expect(save.disabled).toBe(true);
    await user.clear(input);
    await user.type(input, ' my-tsmixer ');
    expect(save.disabled).toBe(true);
    await user.type(input, '2');
    expect(save.disabled).toBe(false);
  });

  it('saves on Enter: the new name in the tile, the dialog closed', async () => {
    const { user, input } = await openRename();
    const renamed = model({ name: 'tsmixer-v2.keras' });
    const fetch = stubApi({
      ...modelsAnswer([renamed, LSTM]),
      'PATCH /api/v1/models/mdl_7f3k2m9qx4': { status: 200, body: renamed },
    });
    await user.clear(input);
    await user.type(input, '  tsmixer-v2 {Enter}');

    await vi.waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(fetch.mock.calls.find(([, init]) => init?.method === 'PATCH')?.[1]?.body).toBe('{"name":"tsmixer-v2"}');
    expect(tiles()[0]?.querySelector('b')?.textContent).toBe('tsmixer-v2.keras');
  });

  it('turns the help line red when the user already has the name', async () => {
    const { user, dialog, input, save } = await openRename();
    stubApi({ 'PATCH /api/v1/models/mdl_7f3k2m9qx4': problem(409, 'model-name-taken', 'Taken.') });
    await user.clear(input);
    await user.type(input, 'lstm-signals');
    await user.click(save);

    const help = await dialog.findByText('You already have a model with this name.');
    expect(help.className).toContain('text-down');
    expect(screen.getByRole('dialog')).toBeDefined();
    await user.type(input, '2');
    expect(dialog.getByText(/^The extension stays/).className).not.toContain('text-down');
  });

  it('changes nothing on Cancel', async () => {
    const { user, dialog, input } = await openRename();
    const fetch = stubApi(modelsAnswer([TSMIXER, LSTM]));
    await user.type(input, 'x');
    await user.click(dialog.getByRole('button', { name: 'Cancel' }));
    await vi.waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe('Delete model', () => {
  async function openDelete(item = TSMIXER) {
    stubApi({ ...session(ARSEN), ...modelsAnswer([TSMIXER, LSTM, DRAFT]) });
    await renderApp('/models');
    await screen.findByText('3 models · 31.4 MB of 100 MB used');
    const user = userEvent.setup();
    await user.click(tile(item.name).getByRole('button', { name: `Delete ${item.name}` }));
    return { user, dialog: within(screen.getByRole('dialog', { name: `Delete ${item.name}?` })) };
  }

  it('says what goes and that it cannot be undone', async () => {
    const { dialog } = await openDelete();
    expect(dialog.getByText('The file goes from your models and frees 14.2 MB. This cannot be undone.')).toBeDefined();
    expect(dialog.getByRole('button', { name: 'Cancel' })).toBeDefined();
    expect(dialog.getByRole('button', { name: 'Delete' }).className).toContain('bg-down');
  });

  it('says the backtests that used it stay', async () => {
    const one = await openDelete(LSTM);
    expect(
      one.dialog.getByText(
        'The file goes from your models and frees 3.0 MB. The backtest that used it stays, with its results. This cannot be undone.',
      ),
    ).toBeDefined();
    cleanup();
    const three = await openDelete(DRAFT);
    expect(
      three.dialog.getByText(/ The 3 backtests that used it stay, with their results\. This cannot be undone\.$/),
    ).toBeDefined();
  });

  it('deletes: the tile goes and the storage frees up', async () => {
    const { user, dialog } = await openDelete();
    const fetch = stubApi({ ...modelsAnswer([LSTM, DRAFT]), 'DELETE /api/v1/models/mdl_7f3k2m9qx4': { status: 204 } });
    await user.click(dialog.getByRole('button', { name: 'Delete' }));

    await vi.waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(fetch).toHaveBeenCalledWith('/api/v1/models/mdl_7f3k2m9qx4', expect.objectContaining({ method: 'DELETE' }));
    expect(tiles()).toHaveLength(2);
    expect(screen.getByText('2 models · 17.2 MB of 100 MB used')).toBeDefined();
  });

  it('stays open with the reason when the API cannot delete', async () => {
    const { user, dialog } = await openDelete();
    stubApi({ 'DELETE /api/v1/models/mdl_7f3k2m9qx4': problem(404, 'not-found', 'You have no such model.') });
    await user.click(dialog.getByRole('button', { name: 'Delete' }));
    expect(await dialog.findByText('You have no such model.')).toBeDefined();
  });
});

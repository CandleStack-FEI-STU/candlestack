// @vitest-environment jsdom
import { cleanup, screen, within } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { ARSEN, sentBody, session, stubApi } from '@/test/api';
import { renderApp, warmUpSettings } from '@/test/app';

beforeAll(warmUpSettings);

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const card = () => within(screen.getByRole('region', { name: 'Profile' }));
const save = () => card().getByRole('button', { name: 'Save' });

describe('Profile', () => {
  it('shows the drawn initials, the name and email, the display name to change, the email and the user ID', async () => {
    stubApi(session(ARSEN));
    await renderApp('/settings/profile');
    expect(card().getByText('AL')).toBeDefined();
    expect(card().getByRole<HTMLInputElement>('textbox', { name: 'Display name' }).value).toBe('Arsen Labovich');
    expect(card().getAllByText('arsen@example.com')).toHaveLength(2);
    expect(card().getByText('usr_7f3k2m9qx4').tagName).toBe('CODE');
    expect(card().queryByRole('button', { name: /copy/i })).toBeNull();
  });

  it('saves a changed name, trimmed, and shows it everywhere', async () => {
    const renamed = { ...ARSEN, display_name: 'Filip Hodoň' };
    const fetch = stubApi({ ...session(ARSEN), 'PATCH /api/v1/me': { status: 200, body: renamed } });
    await renderApp('/settings/profile');
    const user = userEvent.setup();
    expect(save()).toHaveProperty('disabled', true);

    const name = card().getByRole('textbox', { name: 'Display name' });
    await user.clear(name);
    await user.type(name, '  Filip Hodoň ');
    await user.click(save());

    await vi.waitFor(() => expect(screen.getByRole('button', { name: 'Account' }).textContent).toBe('FH'));
    expect(sentBody(fetch, 'PATCH /api/v1/me')).toEqual({ display_name: 'Filip Hodoň' });
    expect(card().getByText('Filip Hodoň', { selector: 'b' })).toBeDefined();
    expect(save()).toHaveProperty('disabled', true);
  });

  it('keeps Save off while the name is empty', async () => {
    stubApi(session(ARSEN));
    await renderApp('/settings/profile');
    const name = card().getByRole('textbox', { name: 'Display name' });
    await userEvent.setup().clear(name);
    expect(name.getAttribute('aria-invalid')).toBe('true');
    expect(save()).toHaveProperty('disabled', true);
  });

  it('says why the name could not be saved and keeps it to try again', async () => {
    stubApi({ ...session(ARSEN), 'PATCH /api/v1/me': { status: 503, body: { detail: 'Down for a minute.' } } });
    await renderApp('/settings/profile');
    const user = userEvent.setup();
    await user.type(card().getByRole('textbox', { name: 'Display name' }), ' Jr');
    await user.keyboard('{Enter}');
    expect((await card().findByRole('alert')).textContent).toBe('Down for a minute.');
    expect(card().getByRole<HTMLInputElement>('textbox', { name: 'Display name' }).value).toBe('Arsen Labovich Jr');
    expect(save()).toHaveProperty('disabled', false);
  });
});

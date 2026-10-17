// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from './dialog';

afterEach(cleanup);

// A dialog with its own trigger that a second button opens too; that button leaves the page while
// the dialog is open when `vanishes`.
function Page({ vanishes = false }: { vanishes?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      {!(vanishes && open) && (
        <button type="button" onClick={() => setOpen(true)}>
          Other
        </button>
      )}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger>Trigger</DialogTrigger>
        <DialogContent aria-describedby={undefined}>
          <DialogHeader>
            <DialogTitle>Dialog</DialogTitle>
          </DialogHeader>
        </DialogContent>
      </Dialog>
    </>
  );
}

async function close(user: ReturnType<typeof userEvent.setup>) {
  await user.keyboard('{Escape}');
  await vi.waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
}

describe('DialogContent', () => {
  it('gives the focus back to the button that opened it', async () => {
    render(<Page />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Other' }));
    await screen.findByRole('dialog');
    await close(user);
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Other' }));
  });

  // A click that leaves the focus on <body> (Safari): the trigger gets it, not the opener before.
  it('leaves the focus to the trigger when the page had it at the opening', async () => {
    render(<Page />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Other' }));
    await close(user);
    (document.activeElement as HTMLElement).blur();
    expect(document.activeElement).toBe(document.body);
    fireEvent.click(screen.getByRole('button', { name: 'Trigger' }));
    await screen.findByRole('dialog');
    await close(user);
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Trigger' }));
  });

  it('leaves the focus to the trigger when the button that opened it is gone', async () => {
    render(<Page vanishes />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Other' }));
    await screen.findByRole('dialog');
    expect(screen.queryByRole('button', { name: 'Other' })).toBeNull();
    await close(user);
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Trigger', hidden: true }));
  });
});

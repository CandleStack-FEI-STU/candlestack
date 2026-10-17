import { DashboardCard } from '@/components/DashboardCard';
import { BUTTON_SIZES, DANGER_BUTTON, OUTLINE_BUTTON } from '@/components/buttonStyles';
import { CancelButton, DangerButton } from '@/components/DialogButtons';
import { WarnIcon } from '@/components/icons';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { useDeleteAccount, useSignOutEverywhere } from '@/features/account';
import { cn } from '@/lib/utils';

import { ActionRow, ErrorNote } from './rows';

// The question before the account goes: what goes with it, Cancel, and the red Delete account.
function DeleteAccountQuestion() {
  const remove = useDeleteAccount();
  return (
    <>
      <DialogHeader>
        <DialogTitle>Delete account?</DialogTitle>
      </DialogHeader>
      <DialogBody>
        <DialogDescription className="text-sm text-foreground">
          This deletes your backtests, uploaded models and your account. This cannot be undone.
        </DialogDescription>
        {remove.error && <ErrorNote>{remove.error.message}</ErrorNote>}
      </DialogBody>
      <DialogFooter>
        <CancelButton />
        <DangerButton disabled={remove.isPending} onClick={() => remove.mutate()}>
          Delete account
        </DangerButton>
      </DialogFooter>
    </>
  );
}

// Delete account asks first, in the app's dialog. The question is made anew each time it opens, so
// a failed attempt is forgotten once it closes.
function DeleteAccount() {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" className={cn(BUTTON_SIZES.sm, OUTLINE_BUTTON, DANGER_BUTTON)}>
          Delete account
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DeleteAccountQuestion />
      </DialogContent>
    </Dialog>
  );
}

// Ending every session and deleting the account, in a card with a red rim. Both leave the app
// signed out on the home page.
export function AccountSection() {
  const signOutEverywhere = useSignOutEverywhere();
  return (
    <DashboardCard icon={WarnIcon} title="Account" danger>
      <ActionRow title="Sign out everywhere" hint="Ends every session on every device.">
        <Button
          type="button"
          variant="outline"
          className={cn(BUTTON_SIZES.sm, OUTLINE_BUTTON)}
          disabled={signOutEverywhere.isPending}
          onClick={() => signOutEverywhere.mutate()}
        >
          Sign out everywhere
        </Button>
      </ActionRow>
      <ActionRow title="Delete account" hint="Deletes your backtests and uploaded models. This cannot be undone.">
        <DeleteAccount />
      </ActionRow>
      {signOutEverywhere.error && <ErrorNote className="mt-2">{signOutEverywhere.error.message}</ErrorNote>}
    </DashboardCard>
  );
}

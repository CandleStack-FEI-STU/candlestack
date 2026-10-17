import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';

import { DashboardCard } from '@/components/DashboardCard';
import { meQueryOptions, updateMe, type Me } from '@/api';
import { ACCENT_BUTTON, BUTTON_SIZES } from '@/components/buttonStyles';
import { HINT } from '@/components/ErrorNote';
import { UserIcon } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Avatar, useSignedInUser } from '@/features/account';
import { cn } from '@/lib/utils';

import { Code, SettingsFooter, SettingsRow } from './rows';

// The API's limit (MeUpdate); it trims the name, so the check does too.
const NAME_MAX = 80;

// The display name being edited. Save sends it once it changed and is not empty (an empty one is
// marked); the API's answer becomes the user everywhere (the header, the menu).
function useDisplayNameForm(saved: string) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(saved);
  const save = useMutation({
    mutationFn: (displayName: string) => updateMe({ display_name: displayName }),
    onSuccess: (me) => queryClient.setQueryData(meQueryOptions().queryKey, me),
  });
  const trimmed = name.trim();
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (trimmed !== '' && trimmed !== saved && !save.isPending) save.mutate(trimmed);
  };
  return { name, setName, empty: trimmed === '', saving: save.isPending, submit, error: save.error?.message };
}

// Who is signed in: the drawn initials (44 px) with the name and email.
function Who({ user }: { user: Me }) {
  return (
    <div className="flex items-center gap-3 pt-1 pb-3">
      <Avatar user={user} className="size-11 text-[15px]/[normal]" />
      <span className="flex min-w-0 flex-col">
        <b className="truncate">{user.display_name}</b>
        <span className={cn('truncate', HINT)}>{user.email}</span>
      </span>
    </div>
  );
}

// The user, then the display name to change, the email from the provider and the public user ID.
export function ProfileSection() {
  const user = useSignedInUser();
  const { name, setName, empty, saving, submit, error } = useDisplayNameForm(user.display_name);
  return (
    <form onSubmit={submit}>
      <DashboardCard icon={UserIcon} title="Profile">
        <Who user={user} />
        <SettingsRow label="Display name">
          <Input
            className="max-w-[260px]"
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={NAME_MAX}
            autoComplete="name"
            aria-label="Display name"
            aria-invalid={empty || undefined}
          />
        </SettingsRow>
        <SettingsRow label="Email">
          <span>{user.email}</span>
        </SettingsRow>
        <SettingsRow label="User ID">
          <Code>{user.id}</Code>
        </SettingsRow>
        <SettingsFooter error={error}>
          <Button type="submit" className={cn(BUTTON_SIZES.sm, ACCENT_BUTTON)} disabled={saving}>
            Save
          </Button>
        </SettingsFooter>
      </DashboardCard>
    </form>
  );
}

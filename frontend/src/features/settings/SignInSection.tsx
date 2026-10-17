import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearch } from '@tanstack/react-router';
import { useEffect, useState } from 'react';

import { DashboardCard } from '@/components/DashboardCard';
import { ApiError, connectUrl, disconnectSignInMethod, meQueryOptions, type Provider, type SignInMethod } from '@/api';
import { ACCENT_BUTTON, BUTTON_SIZES, OUTLINE_BUTTON } from '@/components/buttonStyles';
import { ErrorNote } from '@/components/ErrorNote';
import { HINT } from '@/components/Hint';
import { KeyIcon } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { useSignedInUser } from '@/features/account';
import { PROVIDER_INFO, PROVIDERS } from '@/features/signin';
import { cn } from '@/lib/utils';
import type { ConnectError } from '@/routes/settingsSections';

import { SettingsLead } from './rows';

// The API returns here after adding a method.
const RETURN_PATH = '/settings/sign-in';

const CONNECT_ERRORS: Record<ConnectError, string> = {
  taken: 'That account already signs in to another CandleStack user.',
  failed: 'Could not connect. Try again.',
};

// Removes a method; the user then has one fewer.
function useDisconnect() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: disconnectSignInMethod,
    onSuccess: (_answer, provider) =>
      queryClient.setQueryData(
        meQueryOptions().queryKey,
        (me) =>
          me && {
            ...me,
            providers: me.providers.filter((connected) => connected !== provider),
            sign_in_methods: me.sign_in_methods.filter((method) => method.provider !== provider),
          },
      ),
  });
}

// How connecting ended, from ?error= when the API sent the browser back here. The address drops
// it at once, so a reload or a shared link does not say it again; the message stays until the
// user does something else here.
function useConnectError() {
  const { error } = useSearch({ from: '/_app/settings/$section' });
  const navigate = useNavigate({ from: '/settings/$section' });
  const [shown, setShown] = useState(error);
  useEffect(() => {
    if (error !== undefined) void navigate({ search: {}, replace: true });
  }, [error, navigate]);
  return { connectError: shown, clearConnectError: () => setShown(undefined) };
}

function disconnectError(error: Error | null): string | undefined {
  if (error === null) return undefined;
  const last = error instanceof ApiError && error.problem === 'last-sign-in-method';
  return last ? 'Keep at least one way to sign in.' : error.message;
}

type RowProps = {
  provider: Provider;
  // The provider's account the user signs in with; undefined while it is not connected.
  method: SignInMethod | undefined;
  // The user's only way in: it cannot be disconnected.
  only: boolean;
  busy: boolean;
  onDisconnect: () => void;
};

// A provider: its mark on a tile, its name over whether it is connected (and as whom), and what to
// do about it.
function ProviderRow({ provider, method, only, busy, onDisconnect }: RowProps) {
  const { name, Mark } = PROVIDER_INFO[provider];
  return (
    <div className="flex items-center gap-3 rounded-lg border px-3 py-2.5">
      <span className="grid size-[34px] flex-none place-items-center rounded-lg bg-muted">
        <Mark className="size-[18px]" />
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <b>{name}</b>
        <span className={cn('truncate', HINT)}>{method ? `Connected · ${method.email}` : 'Not connected'}</span>
      </span>
      {method ? (
        <Button
          type="button"
          variant="outline"
          className={cn(BUTTON_SIZES.sm, OUTLINE_BUTTON)}
          disabled={only || busy}
          title={only ? 'Your only way to sign in' : undefined}
          onClick={onDisconnect}
        >
          Disconnect
        </Button>
      ) : (
        <Button asChild className={cn(BUTTON_SIZES.sm, ACCENT_BUTTON)}>
          <a href={connectUrl(provider, RETURN_PATH)}>Connect</a>
        </Button>
      )}
    </div>
  );
}

// GitHub and Google, each connected or not. Connect leaves for the provider and comes back here;
// Disconnect removes it, except the last one.
export function SignInSection() {
  const user = useSignedInUser();
  const { connectError, clearConnectError } = useConnectError();
  const disconnect = useDisconnect();
  const error = disconnectError(disconnect.error) ?? (connectError && CONNECT_ERRORS[connectError]);
  return (
    <DashboardCard icon={KeyIcon} title="Sign-in">
      <SettingsLead>Sign in with either. Keep at least one connected.</SettingsLead>
      <div className="flex flex-col gap-2">
        {PROVIDERS.map((provider) => (
          <ProviderRow
            key={provider}
            provider={provider}
            method={user.sign_in_methods.find((method) => method.provider === provider)}
            only={user.sign_in_methods.length === 1}
            busy={disconnect.isPending}
            onDisconnect={() => {
              clearConnectError();
              disconnect.mutate(provider);
            }}
          />
        ))}
      </div>
      {error && <ErrorNote className="mt-2">{error}</ErrorNote>}
    </DashboardCard>
  );
}

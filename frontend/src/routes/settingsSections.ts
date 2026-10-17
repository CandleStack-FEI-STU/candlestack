import type { SearchSchemaInput } from '@tanstack/react-router';

// /settings/<section>: the sections of Settings, in the order of their tabs. /settings opens the
// first; an unknown one opens it too.
export const SETTINGS_SECTIONS = [
  'profile',
  'sign-in',
  'backtest-defaults',
  'appearance',
  'data-and-storage',
  'api-and-mcp',
  'account',
] as const;

export type SettingsSection = (typeof SETTINGS_SECTIONS)[number];

export const FIRST_SECTION: SettingsSection = 'profile';

export function isSettingsSection(value: string): value is SettingsSection {
  return (SETTINGS_SECTIONS as readonly string[]).includes(value);
}

// The sections that show the account's preferences, which their route loads before they show.
export function showsPreferences(section: SettingsSection): boolean {
  return section === 'backtest-defaults' || section === 'appearance';
}

// ?error=taken|failed: how adding a sign-in method ended when the API sent the browser back to
// /settings/sign-in. taken: the provider's account already signs in to another user. failed: the
// provider or the API failed.
export type ConnectError = 'taken' | 'failed';

export type SettingsSearch = { error?: ConnectError };

// Anything else is dropped; the key is always set, undefined included, as the router keeps search
// params a route does not return (signInSearch.ts).
export function validateSettingsSearch(search: { error?: unknown } & SearchSchemaInput): SettingsSearch {
  return { error: search.error === 'taken' || search.error === 'failed' ? search.error : undefined };
}

import { Link } from '@tanstack/react-router';
import { Code, LogOut } from 'lucide-react';

import type { Me } from '@/api';
import { HomeIcon, SettingsIcon } from '@/components/icons';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

import { Avatar } from './Avatar';
import { useSignOut } from './useLeaveAccount';

// Who is signed in, then the way to Settings, the home page and the API docs and, in red under a
// line, Sign out.
function AccountMenuItems({ user }: { user: Me }) {
  const signOut = useSignOut();
  return (
    <>
      <DropdownMenuLabel className="mb-1 flex flex-col border-b">
        <span className="truncate font-medium">{user.display_name}</span>
        <span className="truncate text-[12.5px] text-muted-foreground">{user.email}</span>
      </DropdownMenuLabel>
      <DropdownMenuItem asChild>
        <Link to="/settings">
          <SettingsIcon />
          Settings
        </Link>
      </DropdownMenuItem>
      <DropdownMenuItem asChild>
        <Link to="/">
          <HomeIcon />
          Home page
        </Link>
      </DropdownMenuItem>
      <DropdownMenuItem asChild>
        {/* Same origin, so stage links to the stage API. */}
        <a href="/api/v1/docs" target="_blank" rel="noopener">
          <Code />
          API docs
        </a>
      </DropdownMenuItem>
      <DropdownMenuSeparator />
      <DropdownMenuItem variant="destructive" onSelect={() => signOut.mutate()}>
        <LogOut />
        Sign out
      </DropdownMenuItem>
    </>
  );
}

// The avatar and its menu (mockups/app, the account menu), in both headers: 240 px wide,
// right-aligned 10 px under the header's 34 px buttons, so 12 px under the 30 px avatar, which
// gets an accent ring while hovered or open.
export function AccountMenu({ user }: { user: Me }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Account"
        className="group shrink-0 rounded-full leading-[0] outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
      >
        <Avatar
          user={user}
          className="group-hover:shadow-[0_0_0_2px_color-mix(in_srgb,var(--accent)_35%,transparent)] group-data-[state=open]:shadow-[0_0_0_2px_color-mix(in_srgb,var(--accent)_35%,transparent)]"
        />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" sideOffset={12} className="w-60 text-sm/[1.5]">
        <AccountMenuItems user={user} />
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

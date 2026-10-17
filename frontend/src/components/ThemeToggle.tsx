import { Sun } from 'lucide-react';

import { GHOST_BUTTON } from '@/components/buttonStyles';
import { MoonIcon } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { useThemeSetting } from '@/features/preferences';
import { cn } from '@/lib/utils';

// .btn.ghost.icon: a 34 px square with the ghost buttons' transparent border, as high as the
// header's other buttons. Signed in, the choice is saved to the account too (Settings, Appearance).
export function ThemeToggle() {
  const { theme, setTheme } = useThemeSetting();
  const label = theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme';

  return (
    <Button
      variant="ghost"
      size="icon"
      className={cn('size-[34px]', GHOST_BUTTON)}
      onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
      aria-label={label}
      title={label}
    >
      {theme === 'dark' ? <Sun /> : <MoonIcon />}
    </Button>
  );
}

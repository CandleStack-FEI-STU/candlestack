import { Sun } from 'lucide-react';

import { GHOST_BUTTON } from '@/components/buttonStyles';
import { MoonIcon } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useTheme } from '@/theme';

// .btn.ghost.icon: a 34 px square with the ghost buttons' transparent border, as high as the
// header's other buttons.
export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const label = theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme';

  return (
    <Button
      variant="ghost"
      size="icon"
      className={cn('size-[34px]', GHOST_BUTTON)}
      onClick={toggle}
      aria-label={label}
      title={label}
    >
      {theme === 'dark' ? <Sun /> : <MoonIcon />}
    </Button>
  );
}

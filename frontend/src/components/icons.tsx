import type { SVGProps } from 'react';

// The design's own line icons where lucide draws a different one (mockups/app: the sidebar, the
// account menu, the theme toggle). The icons lucide draws the same way (the dashboard's grid, the
// API docs' brackets, sign out's door, the plus, the sun) stay lucide's. Same frame as lucide's:
// a 24 px grid, 2 px round strokes in the text colour, 24 px unless a class sizes it.

type IconProps = Omit<SVGProps<SVGSVGElement>, 'children'>;

function Icon({ children, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="24"
      height="24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  );
}

// Backtests: a line rising to an arrow.
export function BacktestsIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M3 17l5-5 4 4 8-8" />
      <path d="M14 8h6v6" />
    </Icon>
  );
}

// Models: a box with sharp corners.
export function ModelsIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12 2l9 5v10l-9 5-9-5V7z" />
      <path d="M12 22V12M21 7l-9 5-9-5" />
    </Icon>
  );
}

// Settings, in the sidebar and the account menu: a ring with eight spokes.
export function SettingsIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3M12 19v3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M2 12h3M19 12h3M4.9 19.1L7 17M17 7l2.1-2.1" />
    </Icon>
  );
}

// Home page: a house with a door.
export function HomeIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M3 10.5L12 3l9 7.5" />
      <path d="M5 9v12h14V9" />
      <path d="M10 21v-6h4v6" />
    </Icon>
  );
}

// The dark theme: a crescent moon.
export function MoonIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
    </Icon>
  );
}

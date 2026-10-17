// The mockups' buttons (.btn) as classes on shadcn's Button, for its variants to look like them.

// .btn: 34 px high with 14 px either side; .btn.lg, in the hero, 42 px with 20 px and 15 px text.
export const BUTTON_SIZES = { default: 'h-[34px] px-3.5', lg: 'h-[42px] px-5 text-[15px]' };

// .btn on the outline variant: no shadow, and a solid background with the full surface on hover
// in both themes, as the buttons stand on the grid.
export const OUTLINE_BUTTON = 'shadow-none dark:bg-background dark:hover:bg-accent';

// .btn.ghost on the ghost variant: a transparent 1 px border, so it lines up with the bordered
// ones, and the full surface on hover in dark too (the variant alone halves it there).
export const GHOST_BUTTON = 'border border-transparent dark:hover:bg-accent';

// .btn.pri on the default variant (Try Backtest, New backtest): the accent border makes the
// button 2 px wider and stays as a rim around the hover color.
export const ACCENT_BUTTON =
  'border border-primary shadow-none hover:bg-[color-mix(in_srgb,var(--accent)_86%,var(--ink))]';

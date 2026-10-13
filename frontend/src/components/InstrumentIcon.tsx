import { instrumentIconUrl } from '@/api';
import { cn } from '@/lib/utils';

// 32 px in the instrument list and the header search, 64 px on the instrument page.
const SIZE = { 32: 'size-8', 64: 'size-16' } as const;

// The instrument's logo, or the backend's square fallback, on a white tile rounded by 10 % of its
// size. The image fills the tile 1 px inside its edge, clipped to its corners, and the 1 px
// hairline is drawn above it, so a logo that fills its whole box (Apple's) never covers it. White
// in both themes, so black logos such as Apple's stay visible in dark mode. The fixed size keeps
// rows from jumping while it loads; the alt is empty because the symbol is always next to it.
export function InstrumentIcon({ id, size }: { id: string; size: keyof typeof SIZE }) {
  return (
    <span
      className={cn(
        'relative block shrink-0 overflow-hidden rounded-[10%] bg-white',
        'after:pointer-events-none after:absolute after:inset-0 after:rounded-[inherit] after:inset-ring after:inset-ring-icon-ring',
        SIZE[size],
      )}
    >
      <img
        src={instrumentIconUrl(id)}
        alt=""
        width={size}
        height={size}
        loading="lazy"
        className="absolute inset-px size-[calc(100%-2px)] rounded-[inherit] object-contain"
      />
    </span>
  );
}

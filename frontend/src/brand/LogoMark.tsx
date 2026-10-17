// The tile alone (the design repository's brand/icon-dark.svg), drawn inline so it takes the
// theme's accent and background like the favicon. Decorative: the page names CandleStack in text.
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden className={className}>
      <rect className="fill-primary" width="32" height="32" rx="7" />
      <g className="fill-background">
        <rect x="10" y="12" width="2" height="14" />
        <rect x="8" y="16" width="6" height="8" />
        <rect x="20" y="6" width="2" height="18" />
        <rect x="18" y="10" width="6" height="10" />
      </g>
    </svg>
  );
}

// The design's 7 px accent dot in a soft 3 px ring: on the Coming soon tag and the sign-in
// page's beta note.
export function AccentDot() {
  return <span className="size-[7px] flex-none rounded-full bg-primary shadow-[0_0_0_3px_var(--accent-soft)]" />;
}

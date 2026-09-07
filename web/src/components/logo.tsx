/**
 * The mark: a page with three lines of transcript, the middle one under a
 * green stroke. It is the product's signature interaction, the cited moment,
 * drawn small. The favicon in `app/icon.svg` is the same drawing.
 */
export function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 28 28" width="28" height="28" aria-hidden="true" className={className}>
      <rect width="28" height="28" rx="7" fill="var(--secondary)" />
      <rect x="5.5" y="11.4" width="17" height="5.2" rx="1.6" fill="var(--primary)" />
      <rect x="7" y="6.8" width="11" height="2.2" rx="1.1" fill="var(--foreground)" />
      <rect x="7" y="12.9" width="14" height="2.2" rx="1.1" fill="var(--primary-foreground)" />
      <rect x="7" y="19" width="8" height="2.2" rx="1.1" fill="var(--foreground)" />
    </svg>
  );
}

/**
 * Speaker colors: light enough to carry dark initials on the dark surfaces,
 * and far from the green that marks what is active or cited.
 */
const PALETTE = ["#d8a0c5", "#d9b36a", "#8fbce6", "#b7a6e6", "#8fd3b0"];

/** One color per speaker, assigned in order of first appearance. */
export function speakerColors(turns: { speaker: string }[]): Map<string, string> {
  const colors = new Map<string, string>();
  for (const { speaker } of turns) {
    if (!colors.has(speaker)) colors.set(speaker, PALETTE[colors.size % PALETTE.length]);
  }
  return colors;
}

/** The letters on a speaker's avatar: the first letter of the first two words, in capitals. */
export function speakerInitials(name: string): string {
  const letters = name
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0].toUpperCase())
    .join("");
  return letters || "?";
}

/** Muted inks for the speaker ticks. Deliberately quiet so the highlight stays the loud color. */
const PALETTE = ["#2F5D8A", "#8A5A2B", "#3E7A5A", "#7A3E6B", "#5A6B7A"];

/** One color per speaker, assigned in order of first appearance. */
export function speakerColors(turns: { speaker: string }[]): Map<string, string> {
  const colors = new Map<string, string>();
  for (const { speaker } of turns) {
    if (!colors.has(speaker)) colors.set(speaker, PALETTE[colors.size % PALETTE.length]);
  }
  return colors;
}

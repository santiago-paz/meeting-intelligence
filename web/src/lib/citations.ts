import type { Citation } from "@/lib/api";

const MARKER = /\[\[([A-Z]\d+)#(\d+)\]\]/g;

/**
 * The answer arrives with inline markers like [[M2#14]]. They become markdown
 * links to a fragment the renderer recognises, so citation chips sit exactly
 * where the model put them and the rest of the markdown renders as usual.
 */
export function markersToLinks(answer: string): string {
  return answer
    .replace(/\]\]\[\[/g, "]] [[") // adjacent markers become separate links
    .replace(MARKER, (_, ref: string, turn: string) => `[${ref}#${turn}](#cite-${ref}-${turn})`);
}

/** The citation key behind a chip link, or null for any other link. */
export function parseCiteHref(href: string | undefined): string | null {
  const match = href?.match(/^#cite-([A-Z]\d+)-(\d+)$/);
  return match ? `${match[1]}#${match[2]}` : null;
}

export function citationKey(citation: { ref: string; turn: number }): string {
  return `${citation.ref}#${citation.turn}`;
}

export type CitedMeeting = Pick<Citation, "ref" | "meeting_id" | "meeting_title">;

/** Each meeting the answer cites, once, in the order it is first cited. */
export function legend(citations: Citation[]): CitedMeeting[] {
  const seen = new Map<string, CitedMeeting>();
  for (const { ref, meeting_id, meeting_title } of citations) {
    if (!seen.has(ref)) seen.set(ref, { ref, meeting_id, meeting_title });
  }
  return [...seen.values()];
}

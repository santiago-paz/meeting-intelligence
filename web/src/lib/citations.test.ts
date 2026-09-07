import { describe, expect, it } from "vitest";

import { citationKey, legend, markersToLinks, parseCiteHref } from "@/lib/citations";

describe("markersToLinks", () => {
  it("turns every [[REF#N]] marker into a link the renderer can recognise", () => {
    expect(markersToLinks("Marco opened it. [[M1#0]] Ana agreed. [[M1#1]]")).toBe(
      "Marco opened it. [M1#0](#cite-M1-0) Ana agreed. [M1#1](#cite-M1-1)",
    );
  });

  it("keeps adjacent markers apart and leaves other brackets alone", () => {
    expect(markersToLinks("both [[M1#23]][[M1#24]] and [not a marker]")).toBe(
      "both [M1#23](#cite-M1-23) [M1#24](#cite-M1-24) and [not a marker]",
    );
  });
});

describe("parseCiteHref", () => {
  it("recovers the citation key from a chip link and rejects anything else", () => {
    expect(parseCiteHref("#cite-M2-14")).toBe("M2#14");
    expect(parseCiteHref("#turn-14")).toBeNull();
    expect(parseCiteHref(undefined)).toBeNull();
  });
});

describe("citationKey and legend", () => {
  const citations = [
    { ref: "M2", meeting_id: "b", meeting_title: "2026-09-08-weekly-sync", turn: 14, speaker: "Marco", start_seconds: 190, timestamp: "00:03:10", text: "Sofía owns it." },
    { ref: "M1", meeting_id: "a", meeting_title: "2026-09-01-q4-planning", turn: 13, speaker: "Marco", start_seconds: 80, timestamp: "00:01:20", text: "Who owns this?" },
    { ref: "M2", meeting_id: "b", meeting_title: "2026-09-08-weekly-sync", turn: 15, speaker: "Sofía", start_seconds: 200, timestamp: "00:03:20", text: "Monday." },
  ];

  it("keys a citation by ref and turn", () => {
    expect(citationKey(citations[0])).toBe("M2#14");
  });

  it("lists each cited meeting once, in order of first citation", () => {
    expect(legend(citations)).toEqual([
      { ref: "M2", meeting_id: "b", meeting_title: "2026-09-08-weekly-sync" },
      { ref: "M1", meeting_id: "a", meeting_title: "2026-09-01-q4-planning" },
    ]);
  });
});

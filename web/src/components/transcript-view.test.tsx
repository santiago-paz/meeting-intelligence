import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TranscriptView } from "@/components/transcript-view";

const turns = [
  { idx: 0, speaker: "Marco", start_seconds: 724, text: "Que hacemos con pricing?" },
  { idx: 1, speaker: "Ana", start_seconds: 731, text: "Lo tengo para fin de mes." },
];

describe("TranscriptView", () => {
  it("renders every turn in order with its timecode, speaker and words", () => {
    render(<TranscriptView turns={turns} />);

    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("00:12:04");
    expect(items[0]).toHaveTextContent("Marco");
    expect(items[0]).toHaveTextContent("Que hacemos con pricing?");
    expect(items[1]).toHaveTextContent("Ana");
  });

  it("anchors each turn by its index so a citation can link straight to it", () => {
    render(<TranscriptView turns={turns} />);

    expect(document.getElementById("turn-1")).toHaveTextContent("Ana");
    expect(screen.getByRole("link", { name: "00:12:11" })).toHaveAttribute("href", "#turn-1");
  });
});

import { describe, expect, it } from "vitest";

import { speakerColors } from "@/lib/speakers";

describe("speakerColors", () => {
  it("assigns one color per speaker in order of first appearance", () => {
    const colors = speakerColors([{ speaker: "Marco" }, { speaker: "Ana" }, { speaker: "Marco" }]);

    expect([...colors.keys()]).toEqual(["Marco", "Ana"]);
    expect(colors.get("Marco")).not.toBe(colors.get("Ana"));
  });

  it("cycles the palette when a meeting has more speakers than colors", () => {
    const colors = speakerColors(["A", "B", "C", "D", "E", "F"].map((speaker) => ({ speaker })));

    expect(colors.get("F")).toBe(colors.get("A"));
  });
});

import { describe, expect, it } from "vitest";

import { formatTimecode } from "@/lib/time";

describe("formatTimecode", () => {
  it("renders seconds as zero-padded HH:MM:SS, matching the transcript files", () => {
    expect(formatTimecode(724)).toBe("00:12:04");
  });

  it("carries hours", () => {
    expect(formatTimecode(3723)).toBe("01:02:03");
  });
});

import { formatDate, pickLocale } from "@/lib/time";

describe("pickLocale", () => {
  it("takes the first language from an Accept-Language header", () => {
    expect(pickLocale("es-AR,es;q=0.9,en;q=0.8")).toBe("es-AR");
  });

  it("falls back when the header is missing or not a locale", () => {
    expect(pickLocale(null)).toBe("en-GB");
    expect(pickLocale("*")).toBe("en-GB");
  });
});

describe("formatDate", () => {
  it("formats an ISO timestamp for the given locale", () => {
    expect(formatDate("2026-09-07T12:00:00Z", "en-GB")).toMatch(/7 Sept 2026/);
  });
});

describe("formatDateTime", () => {
  it("shows the date and the time in the reader's locale", async () => {
    const { formatDateTime } = await import("@/lib/time");

    expect(formatDateTime("2026-09-07T13:05:00Z", "en-GB", "UTC")).toBe("7 Sept 2026, 13:05");
  });
});

import type { TestModeStatus } from "@/lib/api";

export const TITLES = [
  "2026-09-01-q4-planning",
  "2026-09-08-weekly-sync",
  "2026-09-15-weekly-sync",
  "2026-09-22-design-review",
  "2026-09-29-retro",
];

/** What GET /test-mode reports on a machine without a key, samples loaded. */
export const status: TestModeStatus = {
  has_key: false,
  samples: { loaded: TITLES, missing: [] },
  questions: [
    { question: "Who leads the pricing page redesign?", type: "lookup" },
    { question: "Are we building the mobile app this quarter?", type: "lookup" },
    { question: "What is the SOC 2 timeline?", type: "temporal" },
    { question: "How many people are we hiring in Q4?", type: "unanswerable" },
  ],
};

import { describe, expect, it } from "vitest";

import type { TraceSummary } from "@/lib/api";
import { formatCost, formatLatency, summarizeTraces } from "@/lib/traces";

function trace(overrides: Partial<TraceSummary> = {}): TraceSummary {
  return {
    trace_id: "t", created_at: "2026-09-07T10:00:00Z", mode: "classic", question: "Q?", model: "claude-opus-5",
    refused: false, citation_count: 2, dropped_citations: 0, input_tokens: 100, output_tokens: 50, cache_read_tokens: 0,
    cost_usd: 0.01, latency_ms: 7000, rounds: 0, tool_call_count: 0, ...overrides,
  };
}

describe("summarizeTraces", () => {
  it("totals questions, cost and refusals, and gives each mode its median latency", () => {
    const summary = summarizeTraces([
      trace({ latency_ms: 7000, cost_usd: 0.01 }),
      trace({ latency_ms: 9000, cost_usd: 0.02, refused: true }),
      trace({ mode: "agentic", latency_ms: 11000, cost_usd: 0.05 }),
    ]);

    expect(summary).toEqual({
      questions: 3,
      refusals: 1,
      cost_usd: 0.08,
      median_latency_ms: { classic: 8000, agentic: 11000 },
    });
  });

  it("copes with nothing answered yet", () => {
    expect(summarizeTraces([])).toEqual({ questions: 0, refusals: 0, cost_usd: 0, median_latency_ms: {} });
  });
});

describe("formatting", () => {
  it("shows cost in dollars with four decimals and latency in seconds", () => {
    expect(formatCost(0.0123)).toBe("$0.0123");
    expect(formatCost(1.5)).toBe("$1.5000");
    expect(formatLatency(8300)).toBe("8.3 s");
    expect(formatLatency(1040)).toBe("1.0 s");
  });
});

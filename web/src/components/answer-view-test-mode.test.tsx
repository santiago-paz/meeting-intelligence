import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnswerView, type Exchange } from "@/components/answer-view";
import type { AskResponse } from "@/lib/api";

const response: AskResponse = {
  trace_id: "t1", mode: "agentic", question: "Who leads it?", model: "claude-opus-5",
  answer: "Ana leads it. [[M1#7]]", refused: false,
  citations: [{ ref: "M1", meeting_id: "abc", meeting_title: "2026-09-01-q4-planning", turn: 7, speaker: "Marco", start_seconds: 79, timestamp: "00:01:19", text: "Ana leads it." }],
  dropped_citations: 0, retrieved: [], input_tokens: 1103, output_tokens: 376, cache_read_tokens: 900, cache_write_tokens: 0,
  cost_usd: 0, latency_ms: 240, index_rows: 69, rounds: 1,
  tool_calls: [{ round: 1, name: "read_turns", input: {}, summary: "M1 turns 4-9", latency_ms: 12 }],
};

function exchange(model: string): Exchange {
  return { id: "t1", question: "Who leads it?", mode: "agentic", response: { ...response, model } };
}

describe("AnswerView for a recorded answer", () => {
  it("marks an answer that came from test mode", () => {
    render(<AnswerView exchange={exchange("test-mode")} />);

    expect(screen.getByRole("article")).toHaveAttribute("data-recorded", "true");
    expect(screen.getByText(/test mode/i)).toBeInTheDocument();
  });

  it("leaves a real answer unmarked", () => {
    render(<AnswerView exchange={exchange("claude-opus-5")} />);

    expect(screen.getByRole("article")).not.toHaveAttribute("data-recorded");
    expect(screen.queryByText(/test mode/i)).toBeNull();
  });
});

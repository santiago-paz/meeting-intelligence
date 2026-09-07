import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AnswerView, type Exchange } from "@/components/answer-view";
import type { AskResponse } from "@/lib/api";

const citations = [
  { ref: "M1", meeting_id: "abc", meeting_title: "2026-09-08-weekly-sync", turn: 0, speaker: "Marco", start_seconds: 724, timestamp: "00:12:04", text: "Arrancamos." },
  { ref: "M1", meeting_id: "abc", meeting_title: "2026-09-08-weekly-sync", turn: 1, speaker: "Ana", start_seconds: 731, timestamp: "00:12:11", text: "Dale, yo mando los mockups." },
];

function response(overrides: Partial<AskResponse> = {}): AskResponse {
  return {
    trace_id: "t1", mode: "agentic", question: "Who spoke?", model: "claude-opus-5",
    answer: "Marco opened it. [[M1#0]] Ana agreed. [[M1#1]]", refused: false, citations, dropped_citations: 0,
    retrieved: [{ ref: "M1", meeting_id: "abc", meeting_title: "2026-09-08-weekly-sync", turn_start: 0, turn_end: 1, similarity: null }],
    input_tokens: 1200, output_tokens: 80, cache_read_tokens: 1000, cache_write_tokens: 0, cost_usd: 0.0123, latency_ms: 8300,
    index_rows: 12, rounds: 1,
    tool_calls: [{ round: 1, name: "read_turns", input: { meeting_ref: "M1", start: 0, end: 1 }, summary: "M1 turns 0-1", latency_ms: 40 }],
    ...overrides,
  };
}

function exchange(overrides: Partial<AskResponse> = {}): Exchange {
  return { id: "x1", question: "Who spoke?", mode: "agentic", response: response(overrides) };
}

describe("AnswerView", () => {
  it("renders the answer with a chip where each marker was", () => {
    render(<AnswerView exchange={exchange()} />);

    const chips = screen.getAllByRole("button", { name: /^Citation/ });
    expect(chips.map((chip) => chip.textContent)).toEqual(["M1 · 00:12:04", "M1 · 00:12:11"]);
    expect(screen.queryByText(/\[\[M1#0\]\]/)).toBeNull();
    expect(screen.getByText(/Marco opened it\./)).toBeInTheDocument();
  });

  it("marks the cited moment when its chip is pressed", () => {
    render(<AnswerView exchange={exchange()} />);

    fireEvent.click(screen.getByRole("button", { name: /Citation M1 turn 1/ }));

    const moments = screen.getByRole("list", { name: "Cited moments" });
    const rows = within(moments).getAllByRole("listitem");
    expect(rows[1]).toHaveAttribute("data-cited", "true");
    expect(rows[0]).toHaveAttribute("data-cited", "false");
    expect(within(rows[1]).getByText("Dale, yo mando los mockups.")).toBeInTheDocument();
  });

  it("links every cited moment to its turn in the transcript and names the meetings", () => {
    render(<AnswerView exchange={exchange()} />);

    const links = screen.getAllByRole("link", { name: /Open transcript/ });
    expect(links.map((link) => link.getAttribute("href"))).toEqual(["/meetings/abc#turn-0", "/meetings/abc#turn-1"]);
    expect(screen.getByText("2026-09-08-weekly-sync")).toBeInTheDocument();
  });

  it("says so when the meetings do not cover the question", () => {
    render(<AnswerView exchange={exchange({ refused: true, citations: [], answer: "The meetings do not cover hiring." })} />);

    expect(screen.getByText("Not in the meetings")).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Cited moments" })).toBeNull();
  });

  it("shows how the answer was made once asked: tool calls, tokens and cost", () => {
    render(<AnswerView exchange={exchange()} />);

    const trigger = screen.getByRole("button", { name: "How it was answered" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("read_turns")).toBeNull();

    fireEvent.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("read_turns")).toBeInTheDocument();
    expect(screen.getByText("M1 turns 0-1")).toBeInTheDocument();
    expect(screen.getByText(/\$0\.0123/)).toBeInTheDocument();
  });
});

describe("AnswerView as a fold", () => {
  it("puts the question on a button that says whether the answer is open", () => {
    render(<AnswerView exchange={exchange()} fold={{ open: false, onToggle: () => {} }} />);

    const toggle = screen.getByRole("button", { name: /^Who spoke\?/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText(/Marco opened it\./)).not.toBeVisible();
    expect(screen.getByText("Cited moments")).not.toBeVisible();
    expect(screen.getByText("How it was answered")).not.toBeVisible();
  });

  it("shows the answer when open", () => {
    render(<AnswerView exchange={exchange()} fold={{ open: true, onToggle: () => {} }} />);

    expect(screen.getByRole("button", { name: /^Who spoke\?/ })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText(/Marco opened it\./)).toBeVisible();
  });

  it("asks to toggle when the question is pressed", () => {
    const onToggle = vi.fn();
    render(<AnswerView exchange={exchange()} fold={{ open: false, onToggle }} />);

    fireEvent.click(screen.getByRole("button", { name: /^Who spoke\?/ }));

    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("is a plain heading over an answer that is always shown when not asked to fold", () => {
    render(<AnswerView exchange={exchange()} />);

    expect(screen.queryByRole("button", { name: /^Who spoke\?/ })).toBeNull();
    expect(screen.getByRole("heading", { level: 2, name: "Who spoke?" })).toBeInTheDocument();
    expect(screen.getByText(/Marco opened it\./)).toBeVisible();
  });
});

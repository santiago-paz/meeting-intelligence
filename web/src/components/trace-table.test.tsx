import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TraceTable } from "@/components/trace-table";
import type { TraceSummary } from "@/lib/api";

const rows: TraceSummary[] = [
  {
    trace_id: "aaa", created_at: "2026-09-07T13:05:00Z", mode: "agentic", question: "What did Diego commit to?",
    model: "claude-opus-5", refused: false, citation_count: 20, dropped_citations: 0, input_tokens: 9000, output_tokens: 800,
    cache_read_tokens: 8000, cost_usd: 0.0601, latency_ms: 17800, rounds: 1, tool_call_count: 5,
  },
  {
    trace_id: "bbb", created_at: "2026-09-07T13:01:00Z", mode: "classic", question: "How many people are we hiring?",
    model: "claude-opus-5", refused: true, citation_count: 0, dropped_citations: 0, input_tokens: 3000, output_tokens: 100,
    cache_read_tokens: 0, cost_usd: 0.0175, latency_ms: 6100, rounds: 0, tool_call_count: 0,
  },
];

describe("TraceTable", () => {
  it("lists every trace with a link to it and its figures", () => {
    render(<TraceTable rows={rows} locale="en-GB" timeZone="UTC" />);

    const table = screen.getByRole("table", { name: "Traces" });
    const links = within(table).getAllByRole("link");
    expect(links.map((link) => [link.textContent, link.getAttribute("href")])).toEqual([
      ["What did Diego commit to?", "/traces/aaa"],
      ["How many people are we hiring?", "/traces/bbb"],
    ]);
    const first = within(table).getAllByRole("row")[1];
    expect(first).toHaveTextContent("agentic");
    expect(first).toHaveTextContent("17.8 s");
    expect(first).toHaveTextContent("$0.0601");
    expect(first).toHaveTextContent("20");
  });

  it("marks a refusal instead of showing zero citations", () => {
    render(<TraceTable rows={rows} locale="en-GB" timeZone="UTC" />);

    const refused = screen.getAllByRole("row")[2];
    expect(refused).toHaveTextContent("not in the meetings");
  });

  it("says so when nothing has been asked yet", () => {
    render(<TraceTable rows={[]} locale="en-GB" timeZone="UTC" />);

    expect(screen.getByText(/No questions yet/)).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });
});

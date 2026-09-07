import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AskPanel } from "@/components/ask-panel";
import { resetExchangeStore } from "@/lib/exchange-store";

const fetchMock = vi.fn();

const answer = {
  trace_id: "t1", mode: "agentic", question: "Who spoke?", model: "claude-opus-5",
  answer: "Marco opened it. [[M1#0]]", refused: false,
  citations: [{ ref: "M1", meeting_id: "abc", meeting_title: "2026-09-08-weekly-sync", turn: 0, speaker: "Marco", start_seconds: 724, timestamp: "00:12:04", text: "Arrancamos." }],
  dropped_citations: 0, retrieved: [], input_tokens: 10, output_tokens: 5, cache_read_tokens: 0, cache_write_tokens: 0,
  cost_usd: 0.01, latency_ms: 900, index_rows: 3, rounds: 1,
  tool_calls: [{ round: 1, name: "read_turns", input: {}, summary: "M1 turns 0-0", latency_ms: 30 }],
};

/** A streaming response whose events arrive one at a time, released by the test. */
function streamed(events: { event: string; data: unknown }[]) {
  const encoder = new TextEncoder();
  let release!: () => void;
  const gate = new Promise<void>((resolve) => (release = resolve));
  const body = new ReadableStream<Uint8Array>({
    async start(controller) {
      const [first, ...rest] = events;
      controller.enqueue(encoder.encode(`event: ${first.event}\ndata: ${JSON.stringify(first.data)}\n\n`));
      await gate;
      for (const e of rest) controller.enqueue(encoder.encode(`event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`));
      controller.close();
    },
  });
  return { response: { ok: true, status: 200, body }, release };
}

function ask(question = "Who spoke?") {
  fireEvent.change(screen.getByLabelText("Question"), { target: { value: question } });
  fireEvent.submit(screen.getByRole("form", { name: "Ask the meetings" }));
}

describe("AskPanel", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    window.sessionStorage.clear();
    resetExchangeStore();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("shows each tool call as it arrives, then the answer", async () => {
    const { response, release } = streamed([
      { event: "tool_call", data: answer.tool_calls[0] },
      { event: "answer", data: answer },
    ]);
    fetchMock.mockResolvedValue(response);
    render(<AskPanel />);

    ask();

    expect(await screen.findByText("M1 turns 0-0")).toBeInTheDocument();
    expect(screen.queryByText(/Marco opened it\./)).toBeNull();
    release();
    expect(await screen.findByText(/Marco opened it\./)).toBeInTheDocument();
    expect(screen.queryByRole("status")).toBeNull();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/ask");
    expect(JSON.parse(init.body)).toEqual({ question: "Who spoke?", mode: "classic" });
  });

  it("sends the chosen mode", async () => {
    const { response, release } = streamed([{ event: "answer", data: answer }]);
    fetchMock.mockResolvedValue(response);
    render(<AskPanel />);

    fireEvent.click(screen.getByLabelText("Agentic"));
    ask();
    release();

    await screen.findByText(/Marco opened it\./);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).mode).toBe("agentic");
  });

  it("shows the server's refusal to start as an alert", async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 503, json: async () => ({ detail: "ANTHROPIC_API_KEY is not set; answering needs it." }) });
    render(<AskPanel />);

    ask();

    expect(await screen.findByRole("alert")).toHaveTextContent("ANTHROPIC_API_KEY is not set");
  });

  it("shows an error event as an alert and stops waiting", async () => {
    const { response, release } = streamed([{ event: "error", data: { detail: "The model declined to answer this question." } }]);
    fetchMock.mockResolvedValue(response);
    render(<AskPanel />);

    ask();
    release();

    expect(await screen.findByRole("alert")).toHaveTextContent("The model declined");
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("asks for a question before sending an empty one", async () => {
    render(<AskPanel />);

    fireEvent.submit(screen.getByRole("form", { name: "Ask the meetings" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Type a question first.");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("keeps earlier answers across a trip to the transcript and back", async () => {
    window.sessionStorage.setItem(
      "ask.exchanges",
      JSON.stringify([{ id: "x0", question: "Who spoke?", mode: "agentic", response: answer }]),
    );

    render(<AskPanel />);

    expect(await screen.findByText(/Marco opened it\./)).toBeInTheDocument();
  });
});

describe("AskPanel with a linked mode", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    window.sessionStorage.clear();
    resetExchangeStore();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("opens on the mode the link asked for", () => {
    render(<AskPanel initialMode="agentic" />);

    expect(screen.getByLabelText("Agentic")).toBeChecked();
  });
});

import { describe, expect, it } from "vitest";

import { readEvents } from "@/lib/sse";

function stream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

async function collect(body: ReadableStream<Uint8Array>) {
  const events = [];
  for await (const event of readEvents(body)) events.push(event);
  return events;
}

describe("readEvents", () => {
  it("yields one event per blank-line-terminated block, whatever the chunking", async () => {
    const events = await collect(
      stream(["event: tool_call\nda", 'ta: {"round":1}\n\nevent: answer\n', 'data: {"mode":"agentic"}\n\n']),
    );

    expect(events).toEqual([
      { event: "tool_call", data: '{"round":1}' },
      { event: "answer", data: '{"mode":"agentic"}' },
    ]);
  });

  it("defaults the event name, joins multi-line data, and skips comments and CRLF", async () => {
    const events = await collect(stream([": keep-alive\r\ndata: first\r\ndata: second\r\n\r\n"]));

    expect(events).toEqual([{ event: "message", data: "first\nsecond" }]);
  });

  it("flushes a last block that the server did not terminate", async () => {
    const events = await collect(stream(["event: error\ndata: {}"]));

    expect(events).toEqual([{ event: "error", data: "{}" }]);
  });
});

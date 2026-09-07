// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { POST } from "@/app/api/ask/route";

const fetchMock = vi.fn();

function ask(body = { question: "Who spoke?", mode: "agentic" }) {
  return new Request("http://web.test/api/ask", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

describe("POST /api/ask", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    process.env.API_URL = "http://api.test";
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
    delete process.env.API_URL;
  });

  it("forwards the question to the streaming endpoint and passes the events through untouched", async () => {
    const events = 'event: tool_call\ndata: {"round":1}\n\nevent: answer\ndata: {"mode":"agentic"}\n\n';
    fetchMock.mockResolvedValue(new Response(events, { status: 200, headers: { "content-type": "text/event-stream" } }));

    const response = await POST(ask());

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toMatch(/^text\/event-stream/);
    expect(await response.text()).toBe(events);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/ask/stream");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ question: "Who spoke?", mode: "agentic" });
  });

  it("passes the API's rejection through with its status and message", async () => {
    fetchMock.mockResolvedValue(Response.json({ detail: "ANTHROPIC_API_KEY is not set; answering needs it." }, { status: 503 }));

    const response = await POST(ask());

    expect(response.status).toBe(503);
    expect((await response.json()).detail).toMatch(/ANTHROPIC_API_KEY/);
  });

  it("answers 502 with a plain message when the API cannot be reached", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));

    const response = await POST(ask());

    expect(response.status).toBe(502);
    expect((await response.json()).detail).toMatch(/reach the API/);
  });
});

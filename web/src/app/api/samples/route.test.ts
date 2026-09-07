// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { POST } from "@/app/api/samples/route";

const fetchMock = vi.fn();

describe("POST /api/samples", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    process.env.API_URL = "http://api.test";
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
    delete process.env.API_URL;
  });

  it("asks the API to load the sample meetings and returns its answer", async () => {
    const loaded = { loaded: [{ id: "abc", title: "2026-09-01-q4-planning", turn_count: 33, chunk_count: 2 }], skipped: [] };
    fetchMock.mockResolvedValue(Response.json(loaded));

    const response = await POST();

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(loaded);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/meetings/samples");
    expect(init.method).toBe("POST");
  });

  it("passes the API's refusal through with its status and message", async () => {
    fetchMock.mockResolvedValue(Response.json({ detail: "fixtures/test-mode.json is missing" }, { status: 503 }));

    const response = await POST();

    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ detail: "fixtures/test-mode.json is missing" });
  });

  it("answers 502 with a plain message when the API cannot be reached", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));

    const response = await POST();

    expect(response.status).toBe(502);
    expect((await response.json()).detail).toMatch(/reach the API/);
  });
});

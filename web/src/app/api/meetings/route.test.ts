// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GET, POST } from "@/app/api/meetings/route";

const fetchMock = vi.fn();

function upload(name = "q4.txt", content = "[00:12:04] Marco: Hola.") {
  const form = new FormData();
  form.append("file", new File([content], name, { type: "text/plain" }));
  return new Request("http://web.test/api/meetings", { method: "POST", body: form });
}

describe("POST /api/meetings", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    process.env.API_URL = "http://api.test";
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
    delete process.env.API_URL;
  });

  it("forwards the file to the API and returns its answer", async () => {
    const created = { id: "abc", title: "q4", turn_count: 1, chunk_count: 1 };
    fetchMock.mockResolvedValue(Response.json(created));

    const response = await POST(upload());

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(created);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/meetings");
    expect(init.method).toBe("POST");
    expect((init.body as FormData).get("file")).toBeInstanceOf(File);
    expect(((init.body as FormData).get("file") as File).name).toBe("q4.txt");
  });

  it("passes the API's rejection through with its status and message", async () => {
    fetchMock.mockResolvedValue(Response.json({ detail: "No speaker turns found." }, { status: 422 }));

    const response = await POST(upload("notes.txt", "no turns here"));

    expect(response.status).toBe(422);
    expect(await response.json()).toEqual({ detail: "No speaker turns found." });
  });

  it("answers 502 with a plain message when the API cannot be reached", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));

    const response = await POST(upload());

    expect(response.status).toBe(502);
    expect((await response.json()).detail).toMatch(/reach the API/);
  });
});

describe("GET /api/meetings", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    process.env.API_URL = "http://api.test";
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
    delete process.env.API_URL;
  });

  it("returns the API's meeting list, for the search", async () => {
    const meetings = [{ id: "abc", title: "q4", created_at: "2026-09-01T00:00:00Z", turn_count: 3 }];
    fetchMock.mockResolvedValue(Response.json(meetings));

    const response = await GET();

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(meetings);
    expect(fetchMock.mock.calls[0][0]).toBe("http://api.test/meetings");
  });

  it("answers 502 with a plain message when the API cannot be reached", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));

    const response = await GET();

    expect(response.status).toBe(502);
    expect((await response.json()).detail).toMatch(/reach the API/);
  });
});

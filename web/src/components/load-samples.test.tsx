import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LoadSamples } from "@/components/load-samples";

const { refresh } = vi.hoisted(() => ({ refresh: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

const fetchMock = vi.fn();

describe("LoadSamples", () => {
  beforeEach(() => vi.stubGlobal("fetch", fetchMock));
  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
    refresh.mockReset();
  });

  it("loads the samples through the web API and refreshes the page", async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => ({ loaded: [], skipped: [] }) });
    render(<LoadSamples />);

    fireEvent.click(screen.getByRole("button", { name: "Load the sample meetings" }));

    await waitFor(() => expect(refresh).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/samples");
    expect(init.method).toBe("POST");
  });

  it("says what is happening while it takes its time", async () => {
    let resolve!: (value: unknown) => void;
    fetchMock.mockReturnValue(new Promise((r) => (resolve = r)));
    render(<LoadSamples />);

    fireEvent.click(screen.getByRole("button", { name: "Load the sample meetings" }));

    expect(await screen.findByRole("button", { name: /Loading/ })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent(/embedding model/);
    resolve({ ok: true, status: 200, json: async () => ({ loaded: [], skipped: [] }) });
    await waitFor(() => expect(refresh).toHaveBeenCalled());
  });

  it("shows the API's message when loading fails", async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 503, json: async () => ({ detail: "fixtures/test-mode.json is missing" }) });
    render(<LoadSamples />);

    fireEvent.click(screen.getByRole("button", { name: "Load the sample meetings" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("fixtures/test-mode.json is missing");
    expect(refresh).not.toHaveBeenCalled();
  });
});

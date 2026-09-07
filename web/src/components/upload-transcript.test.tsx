import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { UploadTranscript } from "@/components/upload-transcript";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const fetchMock = vi.fn();

function chooseFileAndSubmit() {
  const input = screen.getByLabelText("Transcript file");
  fireEvent.change(input, {
    target: { files: [new File(["[00:12:04] Marco: Hola."], "q4.txt", { type: "text/plain" })] },
  });
  fireEvent.submit(screen.getByRole("form", { name: "Upload a transcript" }));
}

describe("UploadTranscript", () => {
  beforeEach(() => vi.stubGlobal("fetch", fetchMock));
  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
    push.mockReset();
  });

  it("opens the new meeting after a successful upload", async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => ({ id: "abc" }) });
    render(<UploadTranscript />);

    chooseFileAndSubmit();

    await waitFor(() => expect(push).toHaveBeenCalledWith("/meetings/abc"));
    expect(fetchMock.mock.calls[0][0]).toBe("/api/meetings");
  });

  it("shows the API's message when the upload is rejected", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: "No speaker turns found." }),
    });
    render(<UploadTranscript />);

    chooseFileAndSubmit();

    expect(await screen.findByRole("alert")).toHaveTextContent("No speaker turns found.");
    expect(push).not.toHaveBeenCalled();
  });

  it("asks for a file before submitting without one", async () => {
    render(<UploadTranscript />);

    fireEvent.submit(screen.getByRole("form", { name: "Upload a transcript" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Choose a transcript file first.");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

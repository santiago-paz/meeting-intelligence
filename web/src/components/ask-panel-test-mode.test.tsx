import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AskPanel } from "@/components/ask-panel";
import { status } from "@/components/test-mode-fixture";
import { resetExchangeStore } from "@/lib/exchange-store";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

const fetchMock = vi.fn();

/** A stream that never ends, so the working state stays on screen. */
function pending() {
  return { ok: true, status: 200, body: new ReadableStream<Uint8Array>({ start() {} }) };
}

describe("AskPanel in test mode", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    window.sessionStorage.clear();
    resetExchangeStore();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("sends the flag with the question and says it is replaying", async () => {
    fetchMock.mockResolvedValue(pending());
    render(<AskPanel testMode={status} />);

    fireEvent.click(screen.getByRole("button", { name: "Who leads the pricing page redesign?" }));

    expect(await screen.findByRole("status")).toHaveTextContent(/[Rr]eplaying/);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/ask");
    expect(JSON.parse(init.body)).toEqual({ question: "Who leads the pricing page redesign?", mode: "classic", test_mode: true });
  });

  it("leaves the flag off when the switch is off", async () => {
    fetchMock.mockResolvedValue(pending());
    render(<AskPanel testMode={{ ...status, has_key: true }} />);

    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Who spoke?" } });
    fireEvent.submit(screen.getByRole("form", { name: "Ask the meetings" }));

    expect(await screen.findByRole("status")).not.toHaveTextContent(/[Rr]eplaying/);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ question: "Who spoke?", mode: "classic" });
  });
});

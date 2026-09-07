import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AskForm } from "@/components/ask-form";
import { status } from "@/components/test-mode-fixture";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

function type(question: string) {
  fireEvent.change(screen.getByLabelText("Question"), { target: { value: question } });
  fireEvent.submit(screen.getByRole("form", { name: "Ask the meetings" }));
}

describe("AskForm test mode", () => {
  it("is on by default when the API has no key, and off when it has one", () => {
    const { unmount } = render(<AskForm busy={false} onAsk={vi.fn()} testMode={status} />);
    expect(screen.getByRole("switch", { name: "Test mode" })).toHaveAttribute("aria-checked", "true");
    unmount();

    render(<AskForm busy={false} onAsk={vi.fn()} testMode={{ ...status, has_key: true }} />);
    expect(screen.getByRole("switch", { name: "Test mode" })).toHaveAttribute("aria-checked", "false");
  });

  it("says why the switch is there, whichever way it is set", () => {
    render(<AskForm busy={false} onAsk={vi.fn()} testMode={{ ...status, has_key: true }} />);

    expect(screen.getByText(/recorded from a real run/)).toBeInTheDocument();
    expect(screen.getByText(/without an API key/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Who leads the pricing page redesign?" })).toBeNull();

    fireEvent.click(screen.getByRole("switch", { name: "Test mode" }));

    expect(screen.getByRole("button", { name: "Who leads the pricing page redesign?" })).toBeInTheDocument();
  });

  it("asks a sample question in the current mode with the flag when one is pressed", () => {
    const onAsk = vi.fn();
    render(<AskForm busy={false} onAsk={onAsk} testMode={status} />);

    fireEvent.click(screen.getByLabelText("Agentic"));
    fireEvent.click(screen.getByRole("button", { name: "What is the SOC 2 timeline?" }));

    expect(onAsk).toHaveBeenCalledWith("What is the SOC 2 timeline?", "agentic", true);
  });

  it("groups the sample questions by what they test", () => {
    render(<AskForm busy={false} onAsk={vi.fn()} testMode={status} />);

    expect(screen.getByRole("list", { name: "Lookup" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Unanswerable" })).toBeInTheDocument();
  });

  it("sends the flag with a typed question only while test mode is on", () => {
    const onAsk = vi.fn();
    render(<AskForm busy={false} onAsk={onAsk} testMode={status} />);

    type("Who leads the pricing page redesign?");
    expect(onAsk).toHaveBeenLastCalledWith("Who leads the pricing page redesign?", "classic", true);

    fireEvent.click(screen.getByRole("switch", { name: "Test mode" }));
    type("Who leads the pricing page redesign?");
    expect(onAsk).toHaveBeenLastCalledWith("Who leads the pricing page redesign?", "classic", false);
  });

  it("asks for the sample meetings first when they are missing", () => {
    render(<AskForm busy={false} onAsk={vi.fn()} testMode={{ ...status, samples: { loaded: [], missing: status.samples.loaded } }} />);

    expect(screen.getByText(/loaded yet/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Load the sample meetings" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Who leads the pricing page redesign?" })).toBeNull();
  });

  it("says when the API could not be reached instead of listing nothing", () => {
    render(<AskForm busy={false} onAsk={vi.fn()} testMode={null} />);

    fireEvent.click(screen.getByRole("switch", { name: "Test mode" }));

    expect(screen.getByText(/reach the API/)).toBeInTheDocument();
  });

  it("holds the sample questions while an answer is on its way", () => {
    render(<AskForm busy onAsk={vi.fn()} testMode={status} />);

    expect(screen.getByRole("button", { name: "Who leads the pricing page redesign?" })).toBeDisabled();
  });
});

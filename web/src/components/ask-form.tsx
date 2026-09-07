"use client";

import { type FormEvent, type KeyboardEvent, useRef, useState } from "react";

import type { AskMode } from "@/lib/api";

const MODES: { value: AskMode; label: string }[] = [
  { value: "classic", label: "Classic" },
  { value: "agentic", label: "Agentic" },
];

export function AskForm({
  busy,
  onAsk,
  initialMode = "classic",
}: {
  busy: boolean;
  onAsk: (question: string, mode: AskMode) => void;
  initialMode?: AskMode;
}) {
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<AskMode>(initialMode);
  const [empty, setEmpty] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) {
      setEmpty(true);
      inputRef.current?.focus();
      return;
    }
    setEmpty(false);
    onAsk(trimmed, mode);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <form aria-label="Ask the meetings" onSubmit={submit} className="flex flex-col gap-3 rounded-lg border border-rule bg-sheet p-4">
      <div className="flex flex-col gap-1.5">
        <label htmlFor="question" className="eyebrow text-ink-muted">
          Question
        </label>
        <textarea
          ref={inputRef}
          id="question"
          name="question"
          rows={2}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder="What did Diego commit to?"
          autoComplete="off"
          aria-invalid={empty || undefined}
          className="w-full resize-y rounded-md border border-rule bg-sheet px-3 py-2 font-display text-base text-ink placeholder:text-ink-muted/70 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ink"
        />
      </div>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <fieldset className="flex flex-col gap-1.5">
          <legend className="eyebrow mb-1.5 text-ink-muted">Mode</legend>
          <div className="inline-flex w-fit rounded-md border border-rule bg-surface p-0.5">
            {MODES.map((option) => (
              <label
                key={option.value}
                className="cursor-pointer rounded-[4px] px-3 py-1 text-xs font-semibold text-ink-muted hover:text-ink has-checked:bg-ink has-checked:text-sheet has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-ink"
              >
                <input
                  type="radio"
                  name="mode"
                  value={option.value}
                  checked={mode === option.value}
                  onChange={() => setMode(option.value)}
                  className="sr-only"
                />
                {option.label}
              </label>
            ))}
          </div>
          <p className="text-xs text-ink-muted">
            {mode === "classic"
              ? "Answers from the eight excerpts closest to the question."
              : "Reads a table of contents, then fetches the turns it needs."}
          </p>
        </fieldset>
        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-ink px-4 py-2 text-sm font-semibold text-sheet hover:bg-ink/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink disabled:opacity-60"
        >
          {busy ? "Answering…" : "Ask"}
        </button>
      </div>
      {empty && (
        <p role="alert" className="text-sm text-alert">
          Type a question first.
        </p>
      )}
    </form>
  );
}

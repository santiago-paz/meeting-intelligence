"use client";

import { type FormEvent, type KeyboardEvent, useId, useRef, useState } from "react";

import { SampleQuestions } from "@/components/sample-questions";
import type { AskMode, TestModeStatus } from "@/lib/api";

const MODES: { value: AskMode; label: string }[] = [
  { value: "classic", label: "Classic" },
  { value: "agentic", label: "Agentic" },
];

/**
 * The question box, the mode switch and the test-mode switch. Test mode
 * replays answers recorded from a real run instead of asking a model, so the
 * app can be tried without an API key; it starts on when the API has no key.
 * A dashed rule separates it from the live part of the form, the same dashed
 * rule a recorded answer wears.
 */
export function AskForm({
  busy,
  onAsk,
  initialMode = "classic",
  testMode,
}: {
  busy: boolean;
  onAsk: (question: string, mode: AskMode, testMode: boolean) => void;
  initialMode?: AskMode;
  /** What the API reports about test mode, or null when it could not be reached. */
  testMode: TestModeStatus | null;
}) {
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<AskMode>(initialMode);
  const [replay, setReplay] = useState(testMode !== null && !testMode.has_key);
  const [empty, setEmpty] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const switchLabelId = useId();
  const switchWhyId = useId();

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) {
      setEmpty(true);
      inputRef.current?.focus();
      return;
    }
    setEmpty(false);
    onAsk(trimmed, mode, replay);
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
      <section aria-labelledby={switchLabelId} className="mt-1 flex flex-col gap-4 border-t border-dashed border-rule pt-4">
        <div className="flex items-start gap-3">
          <button
            type="button"
            role="switch"
            aria-checked={replay}
            aria-labelledby={switchLabelId}
            aria-describedby={switchWhyId}
            onClick={() => setReplay((current) => !current)}
            className="group relative mt-0.5 h-5 w-9 shrink-0 cursor-pointer rounded-full border border-rule bg-surface transition-colors hover:border-ink-muted aria-checked:border-ink aria-checked:bg-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink motion-reduce:transition-none"
          >
            <span
              aria-hidden="true"
              className="absolute top-0.5 left-0.5 size-3.5 rounded-full bg-ink-muted transition-transform group-aria-checked:translate-x-4 group-aria-checked:bg-sheet motion-reduce:transition-none"
            />
          </button>
          <div className="flex flex-col gap-1">
            <span id={switchLabelId} className="text-sm font-semibold text-ink">
              Test mode
            </span>
            <p id={switchWhyId} className="max-w-[62ch] text-xs leading-relaxed text-ink-muted">
              Replays answers recorded from a real run of this app, so it can be tried without an API key and nothing is
              spent. Only the sample questions below are recorded; retrieval, the citation check and the trace still run
              for real, and only the model’s words are played back.
            </p>
          </div>
        </div>
        {replay && (
          <SampleQuestions status={testMode} busy={busy} onPick={(picked) => onAsk(picked, mode, true)} />
        )}
      </section>
    </form>
  );
}

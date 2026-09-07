"use client";

import { RadioGroup as RadioGroupPrimitive } from "radix-ui";
import { type FormEvent, type KeyboardEvent, useId, useRef, useState } from "react";

import { SampleQuestions } from "@/components/sample-questions";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Label } from "@/components/ui/label";
import { RadioGroup } from "@/components/ui/radio-group";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { AskMode, TestModeStatus } from "@/lib/api";

const MODES: { value: AskMode; label: string; hint: string }[] = [
  { value: "classic", label: "Classic", hint: "Answers from the eight excerpts closest to the question." },
  { value: "agentic", label: "Agentic", hint: "Reads a table of contents, then fetches the turns it needs." },
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
  const modeId = useId();
  const switchId = useId();
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
    <form aria-label="Ask the meetings" onSubmit={submit} className="flex flex-col gap-4 rounded-xl border bg-card p-4 text-card-foreground">
      <Field>
        <FieldLabel htmlFor="question" className="eyebrow text-muted-foreground">
          Question
        </FieldLabel>
        <Textarea
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
          className="min-h-16 resize-y text-base"
        />
      </Field>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <fieldset className="flex min-w-0 flex-col gap-2">
          <legend className="eyebrow mb-2 text-muted-foreground">Mode</legend>
          <RadioGroup
            name="mode"
            value={mode}
            onValueChange={(value) => setMode(value as AskMode)}
            className="flex w-fit gap-0 rounded-lg border bg-background p-0.5"
          >
            {MODES.map((option) => (
              <span key={option.value} className="relative">
                <RadioGroupPrimitive.Item id={`${modeId}-${option.value}`} value={option.value} className="peer sr-only" />
                <Label
                  htmlFor={`${modeId}-${option.value}`}
                  className="cursor-pointer rounded-md px-3 py-1 text-xs font-semibold text-muted-foreground hover:text-foreground peer-focus-visible:ring-2 peer-focus-visible:ring-ring/60 peer-data-checked:bg-secondary peer-data-checked:text-foreground"
                >
                  {option.label}
                </Label>
              </span>
            ))}
          </RadioGroup>
          <p className="text-xs text-muted-foreground">{MODES.find((option) => option.value === mode)?.hint}</p>
        </fieldset>
        <Button type="submit" disabled={busy}>
          {busy ? "Answering…" : "Ask"}
        </Button>
      </div>
      {empty && <FieldError>Type a question first.</FieldError>}
      <section aria-labelledby={switchLabelId} className="mt-1 flex flex-col gap-4 border-t border-dashed pt-4">
        <div className="flex items-start gap-3">
          <Switch
            id={switchId}
            checked={replay}
            onCheckedChange={setReplay}
            aria-labelledby={switchLabelId}
            aria-describedby={switchWhyId}
            className="mt-0.5"
          />
          <div className="flex flex-col gap-1">
            <Label id={switchLabelId} htmlFor={switchId} className="text-sm font-semibold">
              Test mode
            </Label>
            <p id={switchWhyId} className="max-w-[62ch] text-xs leading-relaxed text-muted-foreground">
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

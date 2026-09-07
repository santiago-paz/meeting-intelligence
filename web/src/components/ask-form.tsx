"use client";

import { ArrowUp } from "lucide-react";
import { Spinner } from "@/components/ui/spinner";
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
    if (busy) return;
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
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <form aria-label="Ask the meetings" onSubmit={submit} className="flex flex-col gap-5 rounded-xl border bg-card p-4 shadow-sm sm:p-6 text-card-foreground">
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
          onChange={(event) => {
            setQuestion(event.target.value);
            if (empty) setEmpty(false);
          }}
          onKeyDown={onKeyDown}
          placeholder="What did Diego commit to?"
          autoComplete="off"
          aria-invalid={empty || undefined}
          aria-describedby={empty ? "question-error" : "question-hint"}
          className="min-h-24 resize-y text-base leading-relaxed"
        />
        <p id="question-hint" className="text-xs text-muted-foreground">Enter to ask · Shift + Enter for a new line</p>
        {empty && <FieldError id="question-error">Type a question first.</FieldError>}
      </Field>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <fieldset className="flex min-w-0 flex-col gap-2">
          <legend id={`${modeId}-label`} className="eyebrow mb-2 text-muted-foreground">Mode</legend>
          <RadioGroup
            name="mode"
            aria-labelledby={`${modeId}-label`}
            value={mode}
            onValueChange={(value) => setMode(value as AskMode)}
            className="flex w-fit gap-0 rounded-lg border bg-background p-0.5"
          >
            {MODES.map((option) => (
              <span key={option.value} className="relative">
                <RadioGroupPrimitive.Item id={`${modeId}-${option.value}`} value={option.value} className="peer sr-only" />
                <Label
                  htmlFor={`${modeId}-${option.value}`}
                  className="cursor-pointer rounded-md px-4 py-2 text-sm font-semibold text-muted-foreground hover:text-foreground peer-focus-visible:ring-2 peer-focus-visible:ring-ring/60 peer-data-[state=checked]:bg-secondary peer-data-[state=checked]:text-foreground peer-data-[state=checked]:shadow-sm"
                >
                  {option.label}
                </Label>
              </span>
            ))}
          </RadioGroup>
          <p className="text-xs text-muted-foreground">{MODES.find((option) => option.value === mode)?.hint}</p>
        </fieldset>
        <Button type="submit" disabled={busy} className="h-10 min-w-24">
          {busy ? <Spinner role="presentation" aria-hidden="true" /> : <ArrowUp aria-hidden="true" />}
          {busy ? "Answering…" : "Ask"}
        </Button>
      </div>
      <section aria-labelledby={switchLabelId} className="flex flex-col gap-4 border-t border-dashed pt-5">
        <div className="flex items-start gap-3">
          <Switch
            id={switchId}
            checked={replay}
            onCheckedChange={setReplay}
            aria-labelledby={switchLabelId}
            aria-describedby={switchWhyId}
            className="mt-0.5"
          />
          <div className="min-w-0 flex-1 flex flex-col gap-1.5">
            <Label id={switchLabelId} htmlFor={switchId} className="text-sm font-semibold">
              Test mode
              <span aria-hidden="true" className={`rounded-md px-1.5 py-0.5 text-[0.6875rem] font-medium ${replay ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground"}`}>{replay ? "On" : "Off"}</span>
            </Label>
            <p id={switchWhyId} className="max-w-[62ch] text-xs leading-relaxed text-muted-foreground">
              Try answers recorded from a real run, without an API key or model costs.
              Only the sample questions are available in test mode. Retrieval, citation checks and traces still run live.
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

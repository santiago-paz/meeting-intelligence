"use client";

import { useId } from "react";

import { LoadSamples } from "@/components/load-samples";
import { Button } from "@/components/ui/button";
import type { TestModeStatus } from "@/lib/api";

/** The golden set's question types, in the order the README lists them, with a label a reader can use. */
const TYPES: [string, string][] = [
  ["lookup", "Lookup"],
  ["aggregation", "Aggregation"],
  ["temporal", "Temporal"],
  ["speaker", "By speaker"],
  ["injection", "Injection attempt"],
  ["distractor", "Distractor"],
  ["unanswerable", "Unanswerable"],
];

/**
 * What test mode can answer: the questions of the golden set, grouped by what
 * each one tests, each a button that asks it. The recorded answers cite the
 * sample meetings, so those have to be in first.
 */
export function SampleQuestions({
  status,
  busy,
  onPick,
}: {
  status: TestModeStatus | null;
  busy: boolean;
  onPick: (question: string) => void;
}) {
  const idPrefix = useId();
  if (status === null) {
    return <p className="text-sm text-muted-foreground">Couldn’t reach the API, so there is nothing to replay. Is it running?</p>;
  }
  const missing = status.samples.missing.length;
  if (missing > 0) {
    return (
      <div className="flex flex-col gap-3">
        <p className="max-w-[60ch] text-sm text-muted-foreground">
          The recorded answers point at the five sample meetings, and {missing === 5 ? "none of them are" : `${missing} of them are not`}{" "}
          loaded yet. Loading them needs no key either.
        </p>
        <LoadSamples />
      </div>
    );
  }
  const groups = TYPES.map(([type, label]) => ({ type, label, questions: status.questions.filter((q) => q.type === type) })).filter(
    (group) => group.questions.length > 0,
  );
  return (
    <div className="grid max-h-[28rem] gap-3 overflow-y-auto overscroll-contain rounded-lg p-1 sm:grid-cols-2">
      {groups.map((group) => (
        <div key={group.type} className="min-w-0 rounded-lg border bg-background/50 p-3">
          <h3 id={`${idPrefix}-${group.type}`} className="eyebrow text-muted-foreground">
            {group.label}
          </h3>
          <ul aria-labelledby={`${idPrefix}-${group.type}`} className="mt-2 flex flex-col gap-1">
            {group.questions.map((q) => (
              <li key={q.question}>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={busy}
                  onClick={() => onPick(q.question)}
                  className="h-auto min-h-9 w-full justify-start px-2 py-2 text-left text-sm font-normal leading-relaxed whitespace-normal break-words hover:bg-accent"
                >
                  {q.question}
                </Button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

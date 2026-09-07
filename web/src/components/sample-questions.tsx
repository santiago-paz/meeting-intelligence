"use client";

import { useId } from "react";

import { LoadSamples } from "@/components/load-samples";
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
    return <p className="text-sm text-ink-muted">Couldn’t reach the API, so there is nothing to replay. Is it running?</p>;
  }
  const missing = status.samples.missing.length;
  if (missing > 0) {
    return (
      <div className="flex flex-col gap-3">
        <p className="max-w-[60ch] text-sm text-ink-muted">
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
    <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
      {groups.map((group) => (
        <div key={group.type}>
          <h3 id={`${idPrefix}-${group.type}`} className="eyebrow text-ink-muted">
            {group.label}
          </h3>
          <ul aria-labelledby={`${idPrefix}-${group.type}`} className="mt-1 flex flex-col">
            {group.questions.map((q) => (
              <li key={q.question}>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => onPick(q.question)}
                  className="-mx-1.5 rounded-md px-1.5 py-1 text-left font-display text-[0.95rem] font-medium text-ink hover:bg-marker/40 hover:text-marker-ink focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ink disabled:opacity-60 disabled:hover:bg-transparent disabled:hover:text-ink"
                >
                  {q.question}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

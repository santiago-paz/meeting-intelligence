"use client";

import { type CSSProperties, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { AskMode, AskResponse, Citation } from "@/lib/api";
import { citationKey, legend, markersToLinks, parseCiteHref } from "@/lib/citations";
import { speakerColors } from "@/lib/speakers";

export type Exchange = { id: string; question: string; mode: AskMode; response: AskResponse };

/**
 * One question and its answer. Every marker the model wrote becomes a chip
 * where it stood; pressing a chip marks the moment it points at in the list
 * of cited moments below, with the same highlighter the transcript uses.
 */
export function AnswerView({ exchange }: { exchange: Exchange }) {
  const { response } = exchange;
  const [selected, setSelected] = useState<string | null>(null);
  const byKey = new Map(response.citations.map((citation) => [citationKey(citation), citation]));
  const meetings = legend(response.citations);
  const colors = speakerColors(response.citations);

  function select(key: string) {
    setSelected(key);
    const row = document.getElementById(rowId(exchange.id, key));
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    row?.scrollIntoView?.({ block: "nearest", behavior: reduced ? "auto" : "smooth" });
  }

  return (
    <article aria-labelledby={`${exchange.id}-question`} className="rounded-lg border border-rule bg-sheet">
      <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-rule/60 px-4 py-3">
        <h2 id={`${exchange.id}-question`} className="min-w-0 break-words font-display text-base font-semibold text-ink">
          {exchange.question}
        </h2>
        <p className="text-xs tabular-nums text-ink-muted">
          {response.mode} · {(response.latency_ms / 1000).toFixed(1)} s
        </p>
      </header>
      <div className="px-4 py-4">
        {response.refused && <p className="eyebrow mb-2 text-marker-ink">Not in the meetings</p>}
        <div className="answer max-w-[68ch] text-[0.95rem] leading-relaxed text-ink">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              a: ({ href, children }) => {
                const key = parseCiteHref(href);
                const citation = key ? byKey.get(key) : undefined;
                if (!key || !citation) return <a href={href}>{children}</a>;
                return <CitationChip citation={citation} pressed={selected === key} onPress={() => select(key)} />;
              },
            }}
          >
            {markersToLinks(response.answer)}
          </ReactMarkdown>
        </div>
      </div>
      {response.citations.length > 0 && (
        <section className="border-t border-rule/60 px-4 py-4">
          <h3 className="eyebrow text-ink-muted">Cited moments</h3>
          <p className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-ink-muted">
            {meetings.map((meeting) => (
              <span key={meeting.ref}>
                <span className="font-semibold text-ink">{meeting.ref}</span> <span>{meeting.meeting_title}</span>
              </span>
            ))}
          </p>
          <ol aria-label="Cited moments" className="mt-3 divide-y divide-rule/60 rounded-md border border-rule">
            {response.citations.map((citation) => {
              const key = citationKey(citation);
              return (
                <li
                  key={key}
                  id={rowId(exchange.id, key)}
                  data-cited={selected === key ? "true" : "false"}
                  className="turn grid scroll-mt-20 grid-cols-[6.5rem_1fr] gap-x-4 gap-y-1 px-3 py-3 lg:scroll-mt-6"
                  style={{ "--speaker": colors.get(citation.speaker) } as CSSProperties}
                >
                  <span className="timecode pt-0.5 text-xs tabular-nums text-ink-muted">
                    {citation.ref} · {citation.timestamp}
                  </span>
                  <span className="eyebrow text-ink-muted before:mr-2 before:inline-block before:size-2.5 before:rounded-[2px] before:bg-(--speaker) before:align-[-1px]">
                    {citation.speaker}
                  </span>
                  <p className="col-start-2 max-w-[62ch] font-serif text-[1.02rem] leading-relaxed break-words text-ink">
                    {citation.text}
                  </p>
                  {/* A plain anchor on purpose: the transcript highlights the turn with CSS :target,
                      which browsers only re-evaluate on a real fragment navigation, not on the
                      pushState a client-side Link performs. */}
                  <a
                    href={`/meetings/${citation.meeting_id}#turn-${citation.turn}`}
                    aria-label={`Open transcript at ${citation.timestamp} in ${citation.meeting_title}`}
                    className="col-start-2 w-fit text-xs font-medium text-ink-muted underline decoration-rule underline-offset-4 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
                  >
                    Open transcript
                  </a>
                </li>
              );
            })}
          </ol>
        </section>
      )}
      <details className="group border-t border-rule/60 px-4 py-3">
        <summary className="eyebrow cursor-pointer list-none text-ink-muted before:mr-2 before:inline-block before:transition-transform before:content-['▸'] group-open:before:rotate-90 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">
          How it was answered
        </summary>
        <HowItWasAnswered response={response} />
      </details>
    </article>
  );
}

function rowId(exchangeId: string, key: string): string {
  return `${exchangeId}-${key.replace("#", "-")}`;
}

function CitationChip({ citation, pressed, onPress }: { citation: Citation; pressed: boolean; onPress: () => void }) {
  return (
    <button
      type="button"
      aria-label={`Citation ${citation.ref} turn ${citation.turn}, ${citation.speaker} at ${citation.timestamp}`}
      aria-pressed={pressed}
      onClick={onPress}
      className="mx-0.5 inline-block rounded-sm border border-rule bg-surface px-1.5 py-px align-baseline text-[0.7rem] font-semibold tabular-nums text-ink-muted hover:border-marker-ink/40 hover:bg-marker/40 hover:text-marker-ink focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ink aria-pressed:border-marker-ink/40 aria-pressed:bg-marker/70 aria-pressed:text-marker-ink"
    >
      {`${citation.ref} · ${citation.timestamp}`}
    </button>
  );
}

function HowItWasAnswered({ response }: { response: AskResponse }) {
  const steps =
    response.mode === "agentic"
      ? response.tool_calls.map((call, i) => ({
          key: `${call.round}-${i}`,
          name: call.name,
          detail: call.summary,
          note: `round ${call.round} · ${call.latency_ms} ms`,
        }))
      : response.retrieved.map((chunk, i) => ({
          key: `${chunk.ref}-${i}`,
          name: "retrieved",
          detail: `${chunk.ref} turns ${chunk.turn_start}-${chunk.turn_end}`,
          note: chunk.similarity === null ? "index" : `similarity ${chunk.similarity.toFixed(2)}`,
        }));
  return (
    <div className="mt-3 flex flex-col gap-3 text-xs text-ink-muted">
      {steps.length > 0 && (
        <ol className="flex flex-col gap-1">
          {steps.map((step) => (
            <li key={step.key} className="grid grid-cols-[7.5rem_1fr_auto] gap-x-3">
              <span className="font-semibold text-ink">{step.name}</span>
              <span className="min-w-0 break-words">{step.detail}</span>
              <span className="tabular-nums">{step.note}</span>
            </li>
          ))}
        </ol>
      )}
      <p className="tabular-nums">
        {response.model} · {response.mode === "agentic" ? `${response.rounds} ${response.rounds === 1 ? "round" : "rounds"} · ` : ""}
        {response.input_tokens.toLocaleString("en")} in, {response.output_tokens.toLocaleString("en")} out,{" "}
        {response.cache_read_tokens.toLocaleString("en")} from cache · ${response.cost_usd.toFixed(4)}
        {response.dropped_citations > 0 && ` · ${response.dropped_citations} unverifiable ${response.dropped_citations === 1 ? "citation" : "citations"} removed`}
      </p>
    </div>
  );
}

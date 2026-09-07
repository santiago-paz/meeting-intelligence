"use client";

import { ArrowUpRight, ChevronRight } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { SpeakerAvatar } from "@/components/speaker-avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Item, ItemActions, ItemContent, ItemDescription, ItemMedia, ItemTitle } from "@/components/ui/item";
import { type AskMode, type AskResponse, type Citation, isRecorded } from "@/lib/api";
import { citationKey, legend, markersToLinks, parseCiteHref } from "@/lib/citations";
import { speakerColors } from "@/lib/speakers";

export type Exchange = { id: string; question: string; mode: AskMode; response: AskResponse };

/** Whether the answer is folded under its question, and what pressing the question does. */
export type Fold = { open: boolean; onToggle: () => void };

/**
 * One question and its answer. Every marker the model wrote becomes a chip
 * where it stood; pressing a chip marks the moment it points at in the list
 * of cited moments below, with the same green the transcript uses.
 * Given a fold, the question is the button that opens and closes the answer;
 * without one (the trace page) the answer is always shown.
 */
export function AnswerView({ exchange, fold }: { exchange: Exchange; fold?: Fold }) {
  const { response } = exchange;
  const questionId = `${exchange.id}-question`;
  const bodyId = `${exchange.id}-answer`;
  const open = fold?.open ?? true;
  // A recorded answer says so where the mode is, and wears a dashed rule instead of a solid one.
  const recorded = isRecorded(response);
  const meta = `${recorded ? "test mode · " : ""}${response.mode} · ${(response.latency_ms / 1000).toFixed(1)} s`;
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
    <article
      aria-labelledby={questionId}
      data-recorded={recorded || undefined}
      className="overflow-clip rounded-xl border bg-card text-card-foreground data-recorded:border-dashed data-recorded:border-primary/40"
    >
      {fold ? (
        <h2 className="sticky top-(--header-height) z-20 rounded-t-xl bg-card text-base font-semibold shadow-[0_1px_0_var(--border)]">
          <button
            type="button"
            aria-expanded={fold.open}
            aria-controls={bodyId}
            onClick={fold.onToggle}
            className="group flex w-full cursor-pointer flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-3 text-left outline-none hover:bg-muted/40 focus-visible:bg-muted/40 focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:ring-inset"
          >
            <span className="flex min-w-0 items-center gap-2">
              <ChevronRight
                aria-hidden="true"
                className="size-4 shrink-0 text-muted-foreground transition-transform group-aria-expanded:rotate-90 motion-reduce:transition-none"
              />
              <span id={questionId} className="min-w-0 break-words">
                {exchange.question}
              </span>
            </span>
            <span className="text-xs font-normal tabular-nums text-muted-foreground">{meta}</span>
          </button>
        </h2>
      ) : (
        <header className="sticky top-(--header-height) z-20 rounded-t-xl bg-card shadow-[0_1px_0_var(--border)] flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-4 py-3">
          <h2 id={questionId} className="min-w-0 text-base font-semibold break-words">
            {exchange.question}
          </h2>
          <p className="text-xs tabular-nums text-muted-foreground">{meta}</p>
        </header>
      )}
      <div id={bodyId} hidden={!open} className="border-t">
        <div className="px-4 py-4">
          {response.refused && (
            <Badge variant="secondary" className="mb-3 text-[0.6875rem] font-semibold tracking-[0.08em] uppercase text-primary">
              Not in the meetings
            </Badge>
          )}
          <div className="answer max-w-[68ch] text-[0.9375rem] leading-relaxed">
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
          <section className="border-t px-4 py-4">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h3 className="eyebrow text-muted-foreground">Cited moments</h3>
              <p className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                {meetings.map((meeting) => (
                  <span key={meeting.ref}>
                    <span className="font-semibold text-foreground">{meeting.ref}</span> <span>{meeting.meeting_title}</span>
                  </span>
                ))}
              </p>
            </div>
            <ol aria-label="Cited moments" className="mt-3 flex flex-col gap-1">
              {response.citations.map((citation) => {
                const key = citationKey(citation);
                return (
                  <Item key={key} asChild size="sm" className="turn scroll-mt-40 items-start">
                    <li id={rowId(exchange.id, key)} data-cited={selected === key ? "true" : "false"}>
                      <ItemMedia>
                        <SpeakerAvatar name={citation.speaker} color={colors.get(citation.speaker)!} size="sm" />
                      </ItemMedia>
                      <ItemContent className="gap-1">
                        <ItemTitle className="flex-wrap gap-x-2 text-xs">
                          <span className="font-semibold">{citation.speaker}</span>
                          <span className="timecode font-normal tabular-nums text-muted-foreground">
                            {citation.ref} · {citation.timestamp}
                          </span>
                        </ItemTitle>
                        <ItemDescription className="line-clamp-none max-w-[62ch] text-[0.9375rem] leading-relaxed text-foreground">
                          {citation.text}
                        </ItemDescription>
                      </ItemContent>
                      <ItemActions className="self-start">
                        {/* A plain anchor on purpose: the transcript highlights the turn with CSS :target,
                            which browsers only re-evaluate on a real fragment navigation, not on the
                            pushState a client-side Link performs. */}
                        <Button asChild variant="ghost" size="xs" className="text-muted-foreground">
                          <a
                            href={`/meetings/${citation.meeting_id}#turn-${citation.turn}`}
                            aria-label={`Open transcript at ${citation.timestamp} in ${citation.meeting_title}`}
                          >
                            Open transcript
                            <ArrowUpRight />
                          </a>
                        </Button>
                      </ItemActions>
                    </li>
                  </Item>
                );
              })}
            </ol>
          </section>
        )}
        <Collapsible className="border-t">
          <CollapsibleTrigger asChild>
            <button
              type="button"
              className="group eyebrow flex w-full cursor-pointer items-center gap-2 px-4 py-3 text-left text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:ring-inset"
            >
              <ChevronRight
                aria-hidden="true"
                className="size-3.5 shrink-0 transition-transform group-data-open:rotate-90 motion-reduce:transition-none"
              />
              How it was answered
            </button>
          </CollapsibleTrigger>
          <CollapsibleContent className="px-4 pb-4">
            <HowItWasAnswered response={response} />
          </CollapsibleContent>
        </Collapsible>
      </div>
    </article>
  );
}

function rowId(exchangeId: string, key: string): string {
  return `${exchangeId}-${key.replace("#", "-")}`;
}

function CitationChip({ citation, pressed, onPress }: { citation: Citation; pressed: boolean; onPress: () => void }) {
  return (
    <Badge
      asChild
      variant="outline"
      className="mx-0.5 h-[1.15rem] cursor-pointer rounded-md px-1.5 align-baseline text-[0.6875rem] font-semibold tabular-nums text-muted-foreground hover:border-primary/40 hover:bg-marker hover:text-foreground aria-pressed:border-primary/50 aria-pressed:bg-marker aria-pressed:text-foreground"
    >
      <button
        type="button"
        aria-label={`Citation ${citation.ref} turn ${citation.turn}, ${citation.speaker} at ${citation.timestamp}`}
        aria-pressed={pressed}
        onClick={onPress}
      >
        {`${citation.ref} · ${citation.timestamp}`}
      </button>
    </Badge>
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
    <div className="flex flex-col gap-3 text-xs text-muted-foreground">
      {steps.length > 0 && (
        <ol className="flex flex-col gap-1">
          {steps.map((step) => (
            <li key={step.key} className="grid grid-cols-[7.5rem_1fr_auto] gap-x-3">
              <span className="font-semibold text-foreground">{step.name}</span>
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

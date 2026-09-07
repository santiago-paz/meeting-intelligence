"use client";

import { useState, useSyncExternalStore } from "react";

import { AnswerView } from "@/components/answer-view";
import { AskForm } from "@/components/ask-form";
import type { AskMode, AskResponse, TestModeStatus, ToolCall } from "@/lib/api";
import { readExchanges, readServerExchanges, subscribeExchanges, writeExchanges } from "@/lib/exchange-store";
import { readEvents } from "@/lib/sse";

type Working = { question: string; mode: AskMode; testMode: boolean; toolCalls: ToolCall[] };

/**
 * The question box and everything it has answered, newest first. While an
 * answer is on its way the tool calls stream in as a log, so the wait reads
 * as work. Answers live in the exchange store, which persists them for the
 * session. Each answer folds under its question: the newest is open, the
 * earlier ones start folded, and a fold the reader sets by hand stays put.
 */
export function AskPanel({ initialMode = "classic", testMode = null }: { initialMode?: AskMode; testMode?: TestModeStatus | null }) {
  const exchanges = useSyncExternalStore(subscribeExchanges, readExchanges, readServerExchanges);
  const [working, setWorking] = useState<Working | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Answers the reader opened or folded by hand, by id. The rest follow the default.
  const [toggled, setToggled] = useState<Record<string, boolean>>({});

  async function ask(question: string, mode: AskMode, inTestMode = false) {
    setError(null);
    setWorking({ question, mode, testMode: inTestMode, toolCalls: [] });
    let response: Response;
    try {
      response = await fetch("/api/ask", {
        method: "POST",
        headers: { "content-type": "application/json" },
        // The flag travels only when it is on; the API's default is off.
        body: JSON.stringify(inTestMode ? { question, mode, test_mode: true } : { question, mode }),
      });
    } catch {
      setError("Couldn’t reach the server. Is it running?");
      setWorking(null);
      return;
    }
    if (!response.ok || !response.body) {
      const data = await response.json().catch(() => ({}));
      setError(data.detail ?? `Asking failed (${response.status}).`);
      setWorking(null);
      return;
    }
    let settled = false;
    try {
      for await (const event of readEvents(response.body)) {
        if (event.event === "tool_call") {
          const call = JSON.parse(event.data) as ToolCall;
          setWorking((current) => current && { ...current, toolCalls: [...current.toolCalls, call] });
        } else if (event.event === "answer") {
          const data = JSON.parse(event.data) as AskResponse;
          writeExchanges([{ id: data.trace_id, question, mode, response: data }, ...readExchanges()]);
          settled = true;
          setWorking(null);
        } else if (event.event === "error") {
          setError((JSON.parse(event.data) as { detail?: string }).detail ?? "Answering failed.");
          settled = true;
          setWorking(null);
        }
      }
      if (!settled) setError("The connection closed before the answer arrived.");
    } catch {
      setError("The connection dropped before the answer arrived.");
    } finally {
      setWorking(null);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <AskForm busy={working !== null} onAsk={ask} initialMode={initialMode} testMode={testMode} />
      {working && (
        <section role="status" aria-live="polite" className="rounded-lg border border-rule bg-sheet px-4 py-3 text-xs text-ink-muted">
          <p className="working font-medium text-ink">
            {working.testMode
              ? "Replaying the recorded run…"
              : working.mode === "agentic"
                ? "Reading the table of contents…"
                : "Reading the closest excerpts…"}
          </p>
          {working.toolCalls.length > 0 && (
            <ol className="mt-2 flex flex-col gap-1">
              {working.toolCalls.map((call, i) => (
                <li key={i} className="grid grid-cols-[7.5rem_1fr_auto] gap-x-3">
                  <span className="font-semibold text-ink">{call.name}</span>
                  <span className="min-w-0 break-words">{call.summary}</span>
                  <span className="tabular-nums">{call.latency_ms} ms</span>
                </li>
              ))}
            </ol>
          )}
        </section>
      )}
      {error && (
        <p role="alert" className="rounded-lg border border-alert/30 bg-sheet px-4 py-3 text-sm text-alert">
          {error}
        </p>
      )}
      {exchanges.length === 0 && !working ? (
        <p className="text-sm text-ink-muted">
          Answers appear here, newest first, each with the moments it cites.
        </p>
      ) : (
        <ol className="flex flex-col gap-6">
          {exchanges.map((exchange, i) => {
            const open = toggled[exchange.id] ?? i === 0;
            return (
              <li key={exchange.id}>
                <AnswerView
                  exchange={exchange}
                  fold={{ open, onToggle: () => setToggled((current) => ({ ...current, [exchange.id]: !open })) }}
                />
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}

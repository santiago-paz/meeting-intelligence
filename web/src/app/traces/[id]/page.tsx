import type { Metadata } from "next";
import { headers } from "next/headers";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AnswerView } from "@/components/answer-view";
import { getTrace } from "@/lib/api";
import { formatDateTime, pickLocale } from "@/lib/time";
import { formatCost, formatLatency } from "@/lib/traces";

export async function generateMetadata(props: PageProps<"/traces/[id]">): Promise<Metadata> {
  const { id } = await props.params;
  const trace = await getTrace(id);
  return { title: trace ? `Trace: ${trace.question}` : "Trace not found" };
}

export default async function TracePage(props: PageProps<"/traces/[id]">) {
  const { id } = await props.params;
  const [trace, locale] = await Promise.all([getTrace(id), headers().then((h) => pickLocale(h.get("accept-language")))]);
  if (!trace) notFound();

  const tokens: [string, string][] = [
    ["Input tokens", trace.input_tokens.toLocaleString("en")],
    ["Output tokens", trace.output_tokens.toLocaleString("en")],
    ["Read from cache", trace.cache_read_tokens.toLocaleString("en")],
    ["Written to cache", trace.cache_write_tokens.toLocaleString("en")],
    ["Cost", formatCost(trace.cost_usd)],
    ["Latency", formatLatency(trace.latency_ms)],
    ["Index rows shown", String(trace.index_rows)],
    ["Citations removed", String(trace.dropped_citations)],
  ];

  return (
    <main id="main" className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 sm:py-12">
      <header className="mb-6">
        <p className="eyebrow text-ink-muted">
          <Link href="/traces" className="hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">
            Traces
          </Link>{" "}
          / trace
        </p>
        <p className="mt-1.5 text-xs tabular-nums text-ink-muted">
          <time dateTime={trace.created_at}>{formatDateTime(trace.created_at, locale)}</time> · {trace.mode} · {trace.model}
        </p>
      </header>
      <AnswerView exchange={{ id: trace.trace_id, question: trace.question, mode: trace.mode, response: trace }} />
      {trace.tool_calls.length > 0 && (
        <section className="mt-8">
          <h2 className="eyebrow text-ink-muted">Tool calls, with arguments</h2>
          <ol className="mt-2 divide-y divide-rule/60 rounded-lg border border-rule bg-sheet">
            {trace.tool_calls.map((call, i) => (
              <li key={i} className="grid gap-x-4 gap-y-1 px-4 py-3 text-xs sm:grid-cols-[5rem_1fr_auto]">
                <span className="text-ink-muted">round {call.round}</span>
                <div className="min-w-0">
                  <span className="font-semibold text-ink">{call.name}</span>
                  <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-words text-ink-muted">{JSON.stringify(call.input)}</pre>
                  <span className="text-ink-muted">{call.summary}</span>
                </div>
                <span className="tabular-nums text-ink-muted">{call.latency_ms} ms</span>
              </li>
            ))}
          </ol>
        </section>
      )}
      <section className="mt-8">
        <h2 className="eyebrow text-ink-muted">Tokens and cost</h2>
        <dl className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {tokens.map(([label, value]) => (
            <div key={label} className="rounded-lg border border-rule bg-sheet px-4 py-3">
              <dt className="eyebrow text-ink-muted">{label}</dt>
              <dd className="mt-1.5 font-display text-lg font-semibold text-ink">{value}</dd>
            </div>
          ))}
        </dl>
      </section>
    </main>
  );
}

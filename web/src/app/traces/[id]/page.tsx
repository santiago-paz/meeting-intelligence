import type { Metadata } from "next";
import { headers } from "next/headers";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AnswerView } from "@/components/answer-view";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
    <main id="main" className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader
        crumb={
          <>
            <Link href="/traces" className="rounded-sm outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/60">
              Traces
            </Link>{" "}
            / trace
          </>
        }
        title="One answer, and how it was made"
        badge="Trace"
        meta={
          <>
            <time dateTime={trace.created_at}>{formatDateTime(trace.created_at, locale)}</time> · {trace.mode} · {trace.model}
          </>
        }
      />
      <AnswerView exchange={{ id: trace.trace_id, question: trace.question, mode: trace.mode, response: trace }} />
      {trace.tool_calls.length > 0 && (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle>Tool calls, with arguments</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="flex flex-col divide-y">
              {trace.tool_calls.map((call, i) => (
                <li key={i} className="grid gap-x-4 gap-y-1 py-3 text-xs first:pt-0 last:pb-0 sm:grid-cols-[5rem_1fr_auto]">
                  <span className="text-muted-foreground">round {call.round}</span>
                  <div className="min-w-0">
                    <span className="font-semibold">{call.name}</span>
                    <pre className="mt-1 overflow-x-auto font-mono break-words whitespace-pre-wrap text-muted-foreground">
                      {JSON.stringify(call.input)}
                    </pre>
                    <span className="text-muted-foreground">{call.summary}</span>
                  </div>
                  <span className="tabular-nums text-muted-foreground">{call.latency_ms} ms</span>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}
      <section className="mt-6">
        <h2 className="eyebrow text-muted-foreground">Tokens and cost</h2>
        <dl className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {tokens.map(([label, value]) => (
            <Card key={label} size="sm" className="gap-1 px-4">
              <dt className="eyebrow text-muted-foreground">{label}</dt>
              <dd className="text-lg font-semibold tracking-tight tabular-nums">{value}</dd>
            </Card>
          ))}
        </dl>
      </section>
    </main>
  );
}

import type { Metadata } from "next";
import { headers } from "next/headers";

import { PageHeader } from "@/components/page-header";
import { TraceTable } from "@/components/trace-table";
import { listTraces } from "@/lib/api";
import { pickLocale } from "@/lib/time";
import { formatCost, formatLatency, summarizeTraces } from "@/lib/traces";

export const metadata: Metadata = { title: "Traces" };

// Live data from the API; render per request, never at build time.
export const dynamic = "force-dynamic";

const LIMIT = 100;

export default async function TracesPage() {
  const [rows, locale] = await Promise.all([
    listTraces(LIMIT),
    headers().then((h) => pickLocale(h.get("accept-language"))),
  ]);
  const totals = summarizeTraces(rows);
  const figures: [string, string][] = [
    ["Questions", String(totals.questions)],
    ["Refusals", String(totals.refusals)],
    ["Spent", formatCost(totals.cost_usd)],
    ...(["classic", "agentic"] as const)
      .filter((mode) => totals.median_latency_ms[mode] !== undefined)
      .map((mode): [string, string] => [`Median ${mode}`, formatLatency(totals.median_latency_ms[mode]!)]),
  ];
  return (
    <main id="main" className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 sm:py-12">
      <PageHeader
        title="Traces"
        lede={`The latest ${LIMIT} questions answered, newest first: what the model read, what it cited, what it cost.`}
      />
      {rows.length > 0 && (
        <dl className="mb-6 flex flex-wrap gap-3">
          {figures.map(([label, value]) => (
            <div key={label} className="min-w-[9rem] flex-1 rounded-lg border border-rule bg-sheet px-4 py-3">
              <dt className="eyebrow text-ink-muted">{label}</dt>
              <dd className="mt-1.5 font-display text-2xl font-bold tracking-tight text-ink">{value}</dd>
            </div>
          ))}
        </dl>
      )}
      <TraceTable rows={rows} locale={locale} />
    </main>
  );
}

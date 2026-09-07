import type { Metadata } from "next";
import { headers } from "next/headers";

import { PageHeader } from "@/components/page-header";
import { TraceTable } from "@/components/trace-table";
import { Card } from "@/components/ui/card";
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
    <main id="main" className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader
        title="Traces"
        badge={rows.length > 0 ? `${rows.length} ${rows.length === 1 ? "question" : "questions"}` : undefined}
        lede={`The latest ${LIMIT} questions answered, newest first: what the model read, what it cited, what it cost.`}
      />
      {rows.length > 0 && (
        <dl className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {figures.map(([label, value]) => (
            <Card key={label} size="sm" className="gap-1 px-4">
              <dt className="eyebrow text-muted-foreground">{label}</dt>
              <dd className="text-2xl font-semibold tracking-tight tabular-nums">{value}</dd>
            </Card>
          ))}
        </dl>
      )}
      <TraceTable rows={rows} locale={locale} />
    </main>
  );
}

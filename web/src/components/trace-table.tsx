import Link from "next/link";

import type { TraceSummary } from "@/lib/api";
import { formatDateTime } from "@/lib/time";
import { formatCost, formatLatency } from "@/lib/traces";

const CELL = "px-3 py-2.5 align-top";
const HEAD = `${CELL} eyebrow text-ink-muted`;
const NUMBER = `${CELL} text-right text-xs tabular-nums text-ink-muted`;

/** The ledger of answered questions. The question is the link; the figures are for scanning. */
export function TraceTable({ rows, locale, timeZone }: { rows: TraceSummary[]; locale: string; timeZone?: string }) {
  if (rows.length === 0) {
    return (
      <p className="text-sm text-ink-muted">
        No questions yet.{" "}
        <Link href="/ask" className="underline decoration-rule underline-offset-4 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">
          Ask one
        </Link>{" "}
        and it shows up here.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-rule bg-sheet">
      <table aria-label="Traces" className="w-full min-w-[40rem] border-collapse text-sm text-ink">
        <thead>
          <tr className="border-b border-rule">
            <th scope="col" className={`${HEAD} text-left`}>When</th>
            <th scope="col" className={`${HEAD} text-left`}>Mode</th>
            <th scope="col" className={`${HEAD} text-left`}>Question</th>
            <th scope="col" className={`${HEAD} text-right`}>Cited</th>
            <th scope="col" className={`${HEAD} text-right`}>Latency</th>
            <th scope="col" className={`${HEAD} text-right`}>Cost</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-rule/60">
          {rows.map((row) => (
            <tr key={row.trace_id} className="hover:bg-marker/20">
              <td className={`${CELL} whitespace-nowrap text-xs tabular-nums text-ink-muted`}>
                <time dateTime={row.created_at}>{formatDateTime(row.created_at, locale, timeZone)}</time>
              </td>
              <td className={`${CELL} text-xs text-ink-muted`}>{row.mode}</td>
              <td className={`${CELL} min-w-0`}>
                <Link
                  href={`/traces/${row.trace_id}`}
                  className="font-display font-semibold text-ink break-words hover:underline hover:decoration-marker-ink hover:underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
                >
                  {row.question}
                </Link>
              </td>
              <td className={NUMBER}>
                {row.refused ? <span className="whitespace-nowrap font-medium text-marker-ink">not in the meetings</span> : row.citation_count}
              </td>
              <td className={`${NUMBER} whitespace-nowrap`}>{formatLatency(row.latency_ms)}</td>
              <td className={`${NUMBER} whitespace-nowrap`}>{formatCost(row.cost_usd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

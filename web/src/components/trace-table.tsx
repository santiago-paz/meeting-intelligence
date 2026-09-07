import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { isRecorded, type TraceSummary } from "@/lib/api";
import { formatDateTime } from "@/lib/time";
import { formatCost, formatLatency } from "@/lib/traces";

const HEAD = "px-3 text-[0.6875rem] font-semibold tracking-[0.08em] uppercase text-muted-foreground";
const CELL = "px-3 py-2.5 align-top";
const NUMBER = `${CELL} text-right text-xs tabular-nums text-muted-foreground`;

/** The ledger of answered questions. The question is the link; the figures are for scanning. */
export function TraceTable({ rows, locale, timeZone }: { rows: TraceSummary[]; locale: string; timeZone?: string }) {
  if (rows.length === 0) {
    return (
      <Empty className="border py-10">
        <EmptyHeader>
          <EmptyTitle>No questions yet</EmptyTitle>
          <EmptyDescription>Ask one and it shows up here, with what the model read and what it cost.</EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button asChild variant="outline">
            <Link href="/ask">
              Ask a question
              <ArrowRight />
            </Link>
          </Button>
        </EmptyContent>
      </Empty>
    );
  }
  return (
    <div className="overflow-hidden rounded-xl border bg-card">
      <Table aria-label="Traces" className="min-w-[44rem]">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className={HEAD}>When</TableHead>
            <TableHead className={HEAD}>Mode</TableHead>
            <TableHead className={HEAD}>Question</TableHead>
            <TableHead className={`${HEAD} text-right`}>Cited</TableHead>
            <TableHead className={`${HEAD} text-right`}>Latency</TableHead>
            <TableHead className={`${HEAD} text-right`}>Cost</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.trace_id}>
              <TableCell className={`${CELL} text-xs tabular-nums text-muted-foreground`}>
                <time dateTime={row.created_at}>{formatDateTime(row.created_at, locale, timeZone)}</time>
              </TableCell>
              <TableCell className={CELL}>
                <Badge variant="outline" className="capitalize">
                  {row.mode}
                </Badge>
                {isRecorded(row) && <span className="mt-1 block text-[0.6875rem] text-muted-foreground">test mode</span>}
              </TableCell>
              <TableCell className={`${CELL} min-w-0 whitespace-normal`}>
                <Link
                  href={`/traces/${row.trace_id}`}
                  className="font-medium break-words underline-offset-4 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring/60"
                >
                  {row.question}
                </Link>
              </TableCell>
              <TableCell className={NUMBER}>
                {row.refused ? <span className="font-medium text-primary">not in the meetings</span> : row.citation_count}
              </TableCell>
              <TableCell className={NUMBER}>{formatLatency(row.latency_ms)}</TableCell>
              <TableCell className={NUMBER}>{formatCost(row.cost_usd)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

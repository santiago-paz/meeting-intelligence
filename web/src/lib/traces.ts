import type { AskMode, TraceSummary } from "@/lib/api";

export type TraceTotals = {
  questions: number;
  refusals: number;
  cost_usd: number;
  median_latency_ms: Partial<Record<AskMode, number>>;
};

/** The figures at the top of the traces page. Latency is a median per mode, because one slow call should not move it. */
export function summarizeTraces(rows: TraceSummary[]): TraceTotals {
  const byMode = new Map<AskMode, number[]>();
  let cost = 0;
  let refusals = 0;
  for (const row of rows) {
    cost += row.cost_usd;
    if (row.refused) refusals += 1;
    byMode.set(row.mode, [...(byMode.get(row.mode) ?? []), row.latency_ms]);
  }
  const median_latency_ms: Partial<Record<AskMode, number>> = {};
  for (const [mode, latencies] of byMode) median_latency_ms[mode] = median(latencies);
  return { questions: rows.length, refusals, cost_usd: Math.round(cost * 1e6) / 1e6, median_latency_ms };
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 1 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

export function formatCost(usd: number): string {
  return `$${usd.toFixed(4)}`;
}

export function formatLatency(ms: number): string {
  return `${(ms / 1000).toFixed(1)} s`;
}

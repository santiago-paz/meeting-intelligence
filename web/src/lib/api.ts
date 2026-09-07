/** Server-side access to the FastAPI service. Only route handlers and server components use this. */

export type Turn = { idx: number; speaker: string; start_seconds: number; text: string };
export type MeetingSummary = { id: string; title: string; created_at: string; turn_count: number };
export type MeetingDetail = { id: string; title: string; created_at: string; turns: Turn[] };

export type AskMode = "classic" | "agentic";
export type Citation = {
  ref: string;
  meeting_id: string;
  meeting_title: string;
  turn: number;
  speaker: string;
  start_seconds: number;
  timestamp: string;
  text: string;
};
export type ToolCall = { round: number; name: string; input: Record<string, unknown>; summary: string; latency_ms: number };
export type RetrievedChunk = {
  ref: string;
  meeting_id: string;
  meeting_title: string;
  turn_start: number;
  turn_end: number;
  similarity: number | null;
};
export type AskResponse = {
  trace_id: string;
  mode: AskMode;
  question: string;
  model: string;
  answer: string;
  refused: boolean;
  citations: Citation[];
  dropped_citations: number;
  retrieved: RetrievedChunk[];
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  cost_usd: number;
  latency_ms: number;
  index_rows: number;
  tool_calls: ToolCall[];
  rounds: number;
};

export function apiUrl(): string {
  return process.env.API_URL ?? "http://localhost:8000";
}

export async function listMeetings(): Promise<MeetingSummary[]> {
  const response = await fetch(`${apiUrl()}/meetings`);
  if (!response.ok) throw new Error(`API responded ${response.status} listing meetings`);
  return response.json();
}

export async function getMeeting(id: string): Promise<MeetingDetail | null> {
  const response = await fetch(`${apiUrl()}/meetings/${id}`);
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`API responded ${response.status} for meeting ${id}`);
  return response.json();
}

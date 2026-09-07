/** Server-side access to the FastAPI service. Only route handlers and server components use this. */

export type Turn = { idx: number; speaker: string; start_seconds: number; text: string };
export type MeetingSummary = { id: string; title: string; created_at: string; turn_count: number };
export type MeetingDetail = { id: string; title: string; created_at: string; turns: Turn[] };

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

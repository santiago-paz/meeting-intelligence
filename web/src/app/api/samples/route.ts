import { apiUrl } from "@/lib/api";

/** Asks the API to load the sample meetings from the recorded run. The browser never talks to the API directly. */
export async function POST() {
  let upstream: Response;
  try {
    upstream = await fetch(`${apiUrl()}/meetings/samples`, { method: "POST" });
  } catch {
    return Response.json({ detail: "Couldn’t reach the API. Is it running?" }, { status: 502 });
  }
  const text = await upstream.text();
  let body: unknown;
  try {
    body = JSON.parse(text);
  } catch {
    body = { detail: text || upstream.statusText };
  }
  return Response.json(body, { status: upstream.status });
}

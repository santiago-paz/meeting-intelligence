import { apiUrl } from "@/lib/api";

/** Forwards a transcript upload to the API. The browser never talks to the API directly. */
export async function POST(request: Request) {
  const form = await request.formData();
  let upstream: Response;
  try {
    upstream = await fetch(`${apiUrl()}/meetings`, { method: "POST", body: form });
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

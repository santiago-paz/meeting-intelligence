import { apiUrl } from "@/lib/api";

/**
 * Forwards a question to the API's event stream and passes the events
 * through as they arrive. The browser never talks to the API directly.
 */
export async function POST(request: Request) {
  const body = await request.text();
  let upstream: Response;
  try {
    upstream = await fetch(`${apiUrl()}/ask/stream`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body,
    });
  } catch {
    return Response.json({ detail: "Couldn’t reach the API. Is it running?" }, { status: 502 });
  }
  if (!upstream.ok || !upstream.body) {
    const text = await upstream.text();
    let detail: unknown;
    try {
      detail = JSON.parse(text);
    } catch {
      detail = { detail: text || upstream.statusText };
    }
    return Response.json(detail, { status: upstream.status });
  }
  return new Response(upstream.body, {
    status: 200,
    headers: { "content-type": "text/event-stream; charset=utf-8", "cache-control": "no-cache" },
  });
}

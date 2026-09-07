"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

type Status = { kind: "idle" } | { kind: "loading" } | { kind: "done" } | { kind: "error"; message: string };

/**
 * Loads the five sample meetings from the recorded run. The transcripts are
 * parsed, chunked and embedded for real; the context headers and the
 * extracted rows come from the recording, so no key is needed and nothing is
 * spent. Once they are in, the page refreshes so the parts rendered on the
 * server see them.
 */
export function LoadSamples() {
  const router = useRouter();
  const [status, setStatus] = useState<Status>({ kind: "idle" });

  async function load() {
    setStatus({ kind: "loading" });
    let response: Response;
    try {
      response = await fetch("/api/samples", { method: "POST" });
    } catch {
      setStatus({ kind: "error", message: "Couldn’t reach the server. Is it running?" });
      return;
    }
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      setStatus({ kind: "error", message: data.detail ?? `Loading failed (${response.status}).` });
      return;
    }
    setStatus({ kind: "done" });
    router.refresh();
  }

  const busy = status.kind === "loading" || status.kind === "done";
  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        onClick={load}
        disabled={busy}
        className="w-fit rounded-md bg-ink px-4 py-2 text-sm font-semibold whitespace-nowrap text-sheet hover:bg-ink/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink disabled:opacity-60"
      >
        {status.kind === "loading" ? "Loading…" : status.kind === "done" ? "Loaded" : "Load the sample meetings"}
      </button>
      {status.kind === "loading" && (
        <p role="status" className="max-w-[40ch] text-xs text-ink-muted">
          Embedding the transcripts on this machine. The first time also downloads the embedding model, so give it a minute.
        </p>
      )}
      {status.kind === "error" && (
        <p role="alert" className="text-sm text-alert">
          {status.message}
        </p>
      )}
    </div>
  );
}

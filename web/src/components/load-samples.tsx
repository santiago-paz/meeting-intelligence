"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { FieldError } from "@/components/ui/field";

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
    <div className="flex flex-col items-start gap-2">
      <Button type="button" variant="outline" onClick={load} disabled={busy}>
        {status.kind === "loading" ? "Loading…" : status.kind === "done" ? "Loaded" : "Load the sample meetings"}
      </Button>
      {status.kind === "loading" && (
        <p role="status" className="max-w-[40ch] text-xs text-muted-foreground">
          Embedding the transcripts on this machine. The first time also downloads the embedding model, so give it a minute.
        </p>
      )}
      {status.kind === "error" && <FieldError>{status.message}</FieldError>}
    </div>
  );
}

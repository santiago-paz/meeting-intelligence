"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useRef, useState } from "react";

type Status = { kind: "idle" } | { kind: "uploading" } | { kind: "error"; message: string };

export function UploadTranscript() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<Status>({ kind: "idle" });

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setStatus({ kind: "error", message: "Choose a transcript file first." });
      inputRef.current?.focus();
      return;
    }
    setStatus({ kind: "uploading" });
    const body = new FormData();
    body.append("file", file);
    let response: Response;
    try {
      response = await fetch("/api/meetings", { method: "POST", body });
    } catch {
      setStatus({ kind: "error", message: "Couldn’t reach the server. Is it running?" });
      return;
    }
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      setStatus({ kind: "error", message: data.detail ?? `Upload failed (${response.status}).` });
      return;
    }
    const { id } = await response.json();
    router.push(`/meetings/${id}`);
  }

  const uploading = status.kind === "uploading";
  return (
    <form
      aria-label="Upload a transcript"
      onSubmit={onSubmit}
      className="flex flex-col gap-3 rounded-md border border-rule bg-sheet p-4 sm:flex-row sm:items-end"
    >
      <div className="flex flex-1 flex-col gap-1.5">
        <label htmlFor="transcript" className="font-mono text-xs uppercase tracking-[0.08em] text-ink-muted">
          Transcript file
        </label>
        <input
          ref={inputRef}
          id="transcript"
          name="file"
          type="file"
          accept=".txt,text/plain"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          className="text-sm text-ink file:mr-3 file:rounded-sm file:border file:border-rule file:bg-surface file:px-3 file:py-1.5 file:font-mono file:text-xs file:text-ink hover:file:bg-marker/40"
        />
        <p className="text-xs text-ink-muted">
          A .txt with one line per turn, like <code translate="no" className="font-mono">[00:12:04] Marco: Hola.</code>
        </p>
      </div>
      <button
        type="submit"
        disabled={uploading}
        className="rounded-sm bg-ink px-4 py-2 font-mono text-xs uppercase tracking-[0.08em] text-sheet hover:bg-ink/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink disabled:opacity-60"
      >
        {uploading ? "Uploading…" : "Upload transcript"}
      </button>
      {status.kind === "error" && (
        <p role="alert" className="text-sm text-alert sm:basis-full">
          {status.message}
        </p>
      )}
    </form>
  );
}

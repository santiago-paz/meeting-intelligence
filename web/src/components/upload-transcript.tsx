"use client";

import { Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { type FormEvent, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { FieldError } from "@/components/ui/field";

type Status = { kind: "idle" } | { kind: "uploading" } | { kind: "error"; message: string };

/**
 * The upload is one button: pressing it opens the file picker, and choosing
 * a file sends it. The form around it is what a keyboard, or a test, submits.
 */
export function UploadTranscript() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const uploading = status.kind === "uploading";

  async function upload(file: File | null) {
    if (uploading) return;
    if (!file) {
      setStatus({ kind: "error", message: "Choose a transcript file first." });
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

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void upload(inputRef.current?.files?.[0] ?? null);
  }

  return (
    <form aria-label="Upload a transcript" onSubmit={onSubmit} className="flex flex-col items-end gap-2">
      <label htmlFor="transcript" className="sr-only">
        Transcript file
      </label>
      <input
        ref={inputRef}
        id="transcript"
        name="file"
        type="file"
        accept=".txt,text/plain"
        tabIndex={-1}
        className="sr-only"
        onChange={(event) => {
          const file = event.currentTarget.files?.[0] ?? null;
          // Cleared so that picking the same file again, after a fix, still counts as a change.
          event.currentTarget.value = "";
          void upload(file);
        }}
      />
      <Button type="button" variant="outline" disabled={uploading} onClick={() => inputRef.current?.click()}>
        <Upload />
        {uploading ? "Uploading…" : "Upload transcript"}
      </Button>
      {status.kind === "error" && <FieldError className="max-w-[18rem] text-right">{status.message}</FieldError>}
    </form>
  );
}

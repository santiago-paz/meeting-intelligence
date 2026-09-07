import { headers } from "next/headers";
import Link from "next/link";

import { UploadTranscript } from "@/components/upload-transcript";
import { listMeetings } from "@/lib/api";
import { formatDate, pickLocale } from "@/lib/time";

// The list is live data from the API; render it per request, never at build time.
export const dynamic = "force-dynamic";

export default async function Home() {
  const [meetings, locale] = await Promise.all([
    listMeetings(),
    headers().then((h) => pickLocale(h.get("accept-language"))),
  ]);
  return (
    <main id="main" className="mx-auto w-full max-w-3xl px-4 py-8 sm:py-12">
      <header className="mb-6">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-balance text-ink">Meetings</h1>
        <p className="mt-1 text-sm text-ink-muted">Upload a transcript and read it as a timeline.</p>
      </header>
      <UploadTranscript />
      {meetings.length === 0 ? (
        <p className="mt-8 text-sm text-ink-muted">
          No meetings yet. The first transcript you upload shows up here.
        </p>
      ) : (
        <ol className="mt-8 divide-y divide-rule/60 rounded-md border border-rule bg-sheet">
          {meetings.map((meeting) => (
            <li key={meeting.id}>
              <Link
                href={`/meetings/${meeting.id}`}
                className="grid grid-cols-[1fr_auto] items-baseline gap-4 px-4 py-3 hover:bg-marker/25 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ink"
              >
                <span className="min-w-0 truncate font-display text-base font-medium text-ink">{meeting.title}</span>
                <span className="font-mono text-xs tabular-nums text-ink-muted">
                  {meeting.turn_count} turns · {formatDate(meeting.created_at, locale)}
                </span>
              </Link>
            </li>
          ))}
        </ol>
      )}
    </main>
  );
}

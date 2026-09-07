import { headers } from "next/headers";
import Link from "next/link";

import { PageHeader } from "@/components/page-header";
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
    <main id="main" className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 sm:py-12">
      <PageHeader title="Meetings" lede="Upload a transcript and read it as a timeline." />
      <UploadTranscript />
      {meetings.length === 0 ? (
        <p className="mt-8 text-sm text-ink-muted">
          No meetings yet. The first transcript you upload shows up here.
        </p>
      ) : (
        <ol className="mt-8 divide-y divide-rule/60 overflow-hidden rounded-lg border border-rule bg-sheet">
          {meetings.map((meeting) => (
            <li key={meeting.id}>
              <Link
                href={`/meetings/${meeting.id}`}
                className="grid grid-cols-[1fr_auto] items-baseline gap-4 px-4 py-3.5 hover:bg-marker/25 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ink"
              >
                <span className="min-w-0 truncate font-display text-base font-semibold text-ink">{meeting.title}</span>
                <span className="text-xs tabular-nums text-ink-muted">
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

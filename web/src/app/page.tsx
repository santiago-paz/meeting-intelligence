import { ArrowRight, MessageSquare } from "lucide-react";
import { headers } from "next/headers";
import Link from "next/link";

import { LoadSamples } from "@/components/load-samples";
import { PageHeader } from "@/components/page-header";
import { UploadTranscript } from "@/components/upload-transcript";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { getTestModeStatus, listMeetings, listTraces } from "@/lib/api";
import { formatDate, formatDateTime, pickLocale } from "@/lib/time";

// The list is live data from the API; render it per request, never at build time.
export const dynamic = "force-dynamic";

const RECENT = 5;

export default async function Home() {
  const [meetings, traces, locale, testMode] = await Promise.all([
    listMeetings(),
    // The ledger is a side panel here; if it cannot be read the page still stands.
    listTraces(RECENT).catch(() => []),
    headers().then((h) => pickLocale(h.get("accept-language"))),
    // The recording may be absent (no fixture); then there is simply nothing to offer.
    getTestModeStatus().catch(() => null),
  ]);
  const samplesMissing = (testMode?.samples.missing.length ?? 0) > 0;
  return (
    <main id="main" className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader
        title="Meetings"
        badge={meetings.length > 0 ? `${meetings.length} ${meetings.length === 1 ? "transcript" : "transcripts"}` : undefined}
        lede="Upload a transcript and read it as a timeline."
      />
      <Card>
        <CardHeader className="border-b max-sm:flex max-sm:flex-col max-sm:gap-3">
          <CardTitle>Transcripts</CardTitle>
          <CardDescription>
            A .txt with one line per turn, like{" "}
            <code translate="no" className="rounded bg-muted px-1.5 py-0.5 font-mono text-[0.8rem] text-foreground">
              [00:12:04] Marco: Hola.
            </code>
          </CardDescription>
          <CardAction>
            <UploadTranscript />
          </CardAction>
        </CardHeader>
        <CardContent>
          {meetings.length === 0 ? (
            <Empty className="py-6">
              <EmptyHeader>
                <EmptyTitle>No meetings yet</EmptyTitle>
                <EmptyDescription>
                  {samplesMissing
                    ? "Load the samples, or upload a transcript; either shows up here."
                    : "The first transcript you upload shows up here."}
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {meetings.map((meeting) => (
                <li key={meeting.id}>
                  <Link
                    href={`/meetings/${meeting.id}`}
                    className="flex items-center gap-3 rounded-lg border bg-background/60 px-3 py-3 transition-colors outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/60"
                  >
                    <span aria-hidden="true" className="flex size-8 shrink-0 items-center justify-center rounded-md bg-sidebar-active text-sm font-semibold text-primary">
                      {meeting.title.trim().charAt(0).toUpperCase() || "M"}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{meeting.title}</span>
                      <span className="block text-xs tabular-nums text-muted-foreground">
                        {meeting.turn_count} turns · {formatDate(meeting.created_at, locale)}
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>
      <div className={`mt-4 grid gap-4 ${samplesMissing ? "lg:grid-cols-2" : ""}`}>
        {samplesMissing && (
          <Card>
            <CardHeader>
              <CardTitle>Sample meetings</CardTitle>
              <CardDescription>
                Five meetings of a fictional product team come with the app, taken from a recorded run: no API key needed,
                nothing spent. Test mode on the Ask page answers questions about them.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <LoadSamples />
            </CardContent>
          </Card>
        )}
        <Card>
          <CardHeader>
            <CardTitle>Recent questions</CardTitle>
          </CardHeader>
          <CardContent>
            {traces.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Nothing asked yet.{" "}
                <Link href="/ask" className="underline underline-offset-4 hover:text-foreground">
                  Ask the meetings
                </Link>{" "}
                and it shows up here.
              </p>
            ) : (
              <>
                <ol className="flex flex-col divide-y">
                  {traces.map((trace) => (
                    <li key={trace.trace_id} className="py-2.5 first:pt-0 last:pb-0">
                      <Link
                        href={`/traces/${trace.trace_id}`}
                        className="group flex items-start gap-3 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
                      >
                        <span aria-hidden="true" className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
                          <MessageSquare className="size-4" />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block text-sm font-medium break-words underline-offset-4 group-hover:underline">{trace.question}</span>
                          <span className="mt-0.5 block text-xs tabular-nums text-muted-foreground">
                            {formatDateTime(trace.created_at, locale)} · {trace.mode} ·{" "}
                            {trace.refused ? "not in the meetings" : `${trace.citation_count} cited`}
                          </span>
                        </span>
                      </Link>
                    </li>
                  ))}
                </ol>
                <Button asChild variant="link" className="mt-3 h-auto px-0 text-foreground">
                  <Link href="/traces">
                    View all traces
                    <ArrowRight />
                  </Link>
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}

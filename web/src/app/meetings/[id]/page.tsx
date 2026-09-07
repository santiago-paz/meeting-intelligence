import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { SpeakerAvatar } from "@/components/speaker-avatar";
import { TranscriptView } from "@/components/transcript-view";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getMeeting } from "@/lib/api";
import { speakerColors } from "@/lib/speakers";
import { formatTimecode } from "@/lib/time";

export async function generateMetadata(props: PageProps<"/meetings/[id]">): Promise<Metadata> {
  const { id } = await props.params;
  const meeting = await getMeeting(id);
  return { title: meeting?.title ?? "Meeting not found" };
}

export default async function MeetingPage(props: PageProps<"/meetings/[id]">) {
  const { id } = await props.params;
  const meeting = await getMeeting(id);
  if (!meeting) notFound();

  const colors = speakerColors(meeting.turns);
  const turnsBySpeaker = new Map<string, number>();
  for (const turn of meeting.turns) {
    turnsBySpeaker.set(turn.speaker, (turnsBySpeaker.get(turn.speaker) ?? 0) + 1);
  }
  const lastTurn = meeting.turns.at(-1);

  return (
    <main id="main" className="mx-auto grid w-full max-w-6xl gap-6 px-4 py-6 sm:px-6 sm:py-8 lg:grid-cols-[minmax(0,1fr)_17rem]">
      <article>
        <PageHeader
          crumb={
            <>
              <Link href="/" className="rounded-sm outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/60">
                Meetings
              </Link>{" "}
              / transcript
            </>
          }
          title={meeting.title}
          badge="Meeting"
          meta={
            <>
              {meeting.turns.length} turns · ends {lastTurn ? formatTimecode(lastTurn.start_seconds) : "00:00:00"} ·{" "}
              {colors.size} {colors.size === 1 ? "speaker" : "speakers"}
            </>
          }
        />
        <Card className="gap-0 py-1">
          <TranscriptView turns={meeting.turns} />
        </Card>
      </article>
      <aside className="lg:sticky lg:top-[calc(var(--header-height)+1.5rem)] lg:self-start">
        <Card size="sm">
          <CardHeader>
            <CardTitle>Speakers</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-2">
              {[...colors].map(([speaker, color]) => (
                <li key={speaker} className="flex items-center justify-between gap-2 text-sm">
                  <span className="flex min-w-0 items-center gap-2">
                    <SpeakerAvatar name={speaker} color={color} size="sm" />
                    <span className="truncate font-medium">{speaker}</span>
                  </span>
                  <span className="text-xs tabular-nums text-muted-foreground">
                    {turnsBySpeaker.get(speaker)} {turnsBySpeaker.get(speaker) === 1 ? "turn" : "turns"}
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
              Each timecode is a link to that moment. Open one and the turn is highlighted.
            </p>
          </CardContent>
        </Card>
      </aside>
    </main>
  );
}

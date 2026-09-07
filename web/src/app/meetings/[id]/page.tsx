import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { TranscriptView } from "@/components/transcript-view";
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
    <main id="main" className="mx-auto grid w-full max-w-6xl gap-8 px-4 py-8 lg:grid-cols-[minmax(0,1fr)_18rem]">
      <article>
        <header className="mb-4">
          <p className="font-mono text-xs uppercase tracking-[0.08em] text-ink-muted">
            <Link href="/" className="hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">
              Meetings
            </Link>{" "}
            / transcript
          </p>
          <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight text-balance break-words text-ink">{meeting.title}</h1>
          <p className="mt-1 font-mono text-xs tabular-nums text-ink-muted">
            {meeting.turns.length} turns · ends {lastTurn ? formatTimecode(lastTurn.start_seconds) : "00:00:00"} ·{" "}
            {colors.size} {colors.size === 1 ? "speaker" : "speakers"}
          </p>
        </header>
        <div className="rounded-md border border-rule bg-sheet px-2 py-1">
          <TranscriptView turns={meeting.turns} />
        </div>
      </article>
      <aside className="lg:sticky lg:top-20 lg:self-start">
        <h2 className="font-mono text-xs uppercase tracking-[0.08em] text-ink-muted">Speakers</h2>
        <ul className="mt-2 divide-y divide-rule/60 rounded-md border border-rule bg-sheet">
          {[...colors].map(([speaker, color]) => (
            <li key={speaker} className="flex items-center justify-between px-3 py-2 text-sm text-ink">
              <span className="flex min-w-0 items-center gap-2">
                <span aria-hidden className="size-2.5 shrink-0 rounded-[2px]" style={{ background: color }} />
                <span className="truncate">{speaker}</span>
              </span>
              <span className="font-mono text-xs tabular-nums text-ink-muted">
                {turnsBySpeaker.get(speaker)} {turnsBySpeaker.get(speaker) === 1 ? "turn" : "turns"}
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-xs leading-relaxed text-ink-muted">
          Each timecode is a link to that moment. Open one and the turn is highlighted.
        </p>
      </aside>
    </main>
  );
}

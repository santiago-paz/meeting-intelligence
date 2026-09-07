import { SpeakerAvatar } from "@/components/speaker-avatar";
import type { Turn } from "@/lib/api";
import { speakerColors } from "@/lib/speakers";
import { formatTimecode } from "@/lib/time";

/**
 * The transcript as a timeline. Every turn is anchored by its index
 * (#turn-12) so a citation can link straight to the moment it quotes,
 * and the timecode in the gutter is that link.
 */
export function TranscriptView({ turns }: { turns: Turn[] }) {
  const colors = speakerColors(turns);
  return (
    <ol className="divide-y divide-border/70">
      {turns.map((turn) => (
        <li
          key={turn.idx}
          id={`turn-${turn.idx}`}
          className="turn grid scroll-mt-20 grid-cols-[4.5rem_auto_1fr] items-start gap-x-3 gap-y-1 rounded-lg px-3 py-3 sm:grid-cols-[5.5rem_auto_1fr] sm:gap-x-4"
        >
          <a
            href={`#turn-${turn.idx}`}
            className="timecode w-fit rounded-sm pt-1 text-xs tabular-nums text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/60"
          >
            {formatTimecode(turn.start_seconds)}
          </a>
          <SpeakerAvatar name={turn.speaker} color={colors.get(turn.speaker)!} size="sm" className="mt-0.5" />
          <div className="min-w-0">
            <p className="text-xs font-semibold">{turn.speaker}</p>
            <p className="mt-0.5 max-w-[62ch] text-[0.9375rem] leading-relaxed break-words">{turn.text}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

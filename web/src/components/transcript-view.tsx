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
          className="turn grid scroll-mt-20 grid-cols-[auto_minmax(0,1fr)] items-start gap-x-3 gap-y-1 rounded-lg px-3 py-3 sm:grid-cols-[5.5rem_auto_1fr] sm:gap-x-4"
        >
          <a
            href={`#turn-${turn.idx}`}
            className="timecode z-10 col-start-2 row-start-1 justify-self-end w-fit rounded-sm pt-0.5 sm:col-start-1 sm:justify-self-start sm:pt-1 text-xs tabular-nums text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/60"
          >
            {formatTimecode(turn.start_seconds)}
          </a>
          <SpeakerAvatar name={turn.speaker} color={colors.get(turn.speaker)!} size="sm" className="col-start-1 row-start-1 mt-0.5 sm:col-start-2" />
          <div className="col-start-2 row-start-1 min-w-0 sm:col-start-3">
            <p className="pr-20 text-xs font-semibold sm:pr-0">{turn.speaker}</p>
            <p className="mt-0.5 max-w-[62ch] text-[0.9375rem] leading-relaxed break-words">{turn.text}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

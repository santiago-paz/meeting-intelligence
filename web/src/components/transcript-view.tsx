import type { CSSProperties } from "react";

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
    <ol className="divide-y divide-rule/60">
      {turns.map((turn) => (
        <li
          key={turn.idx}
          id={`turn-${turn.idx}`}
          className="turn grid scroll-mt-20 grid-cols-[5.5rem_1fr] gap-x-4 gap-y-1 rounded-md px-2 py-3 sm:grid-cols-[6.5rem_1fr] lg:scroll-mt-6"
          style={{ "--speaker": colors.get(turn.speaker) } as CSSProperties}
        >
          <a
            href={`#turn-${turn.idx}`}
            className="timecode row-span-2 pt-1 text-xs tabular-nums text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          >
            {formatTimecode(turn.start_seconds)}
          </a>
          <span className="eyebrow text-ink-muted before:mr-2 before:inline-block before:size-2.5 before:rounded-[2px] before:bg-(--speaker) before:align-[-1px]">
            {turn.speaker}
          </span>
          <p className="max-w-[62ch] font-serif text-[1.05rem] leading-relaxed break-words text-ink">{turn.text}</p>
        </li>
      ))}
    </ol>
  );
}

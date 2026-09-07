import { speakerInitials } from "@/lib/speakers";
import { cn } from "@/lib/utils";

const SIZE = { sm: "size-6 text-[0.625rem]", default: "size-8 text-xs", lg: "size-10 text-sm" };

/**
 * A speaker's initials on a colored disc, the way people appear in the
 * console this design follows. A plain span rather than the Avatar
 * primitive: there is no image to load, and a transcript renders hundreds of
 * these on the server.
 */
export function SpeakerAvatar({
  name,
  color,
  size = "default",
  className,
}: {
  name: string;
  color: string;
  size?: keyof typeof SIZE;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={cn("inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-[#111213] select-none", SIZE[size], className)}
      style={{ background: color }}
    >
      {speakerInitials(name)}
    </span>
  );
}

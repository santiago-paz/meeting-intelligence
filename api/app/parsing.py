import re

from app.models import Turn


class TranscriptParseError(ValueError):
    """Raised when no speaker turn can be recognised in the input."""


# One turn per line: "[HH:MM:SS] Speaker: text" or "[MM:SS] Speaker: text".
# The speaker is everything up to the first colon, so colons inside the
# utterance survive.
_TURN_LINE = re.compile(r"^\[(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\]\s+([^:]+):\s*(.*)$")


def parse_transcript(raw: str) -> list[Turn]:
    """Split a transcript into ordered speaker turns.

    Lines that carry a timestamp and a speaker label start a new turn. Any
    other non-blank line is treated as a wrapped continuation of the turn
    above it, and anything before the first turn (title, date, attendees)
    is ignored. Raises TranscriptParseError if no turn is found at all.
    """
    turns: list[Turn] = []
    for line in raw.splitlines():
        match = _TURN_LINE.match(line)
        if match:
            hours, minutes, seconds, speaker, text = match.groups()
            turns.append(
                Turn(
                    idx=len(turns),
                    speaker=speaker.strip(),
                    start_seconds=_to_seconds(hours, minutes, seconds),
                    text=text.strip(),
                )
            )
        elif line.strip() and turns:
            turns[-1].text = f"{turns[-1].text} {line.strip()}".strip()
    if not turns:
        raise TranscriptParseError(
            "No speaker turns found. Expected lines like '[00:12:04] Speaker: text'."
        )
    return turns


def _to_seconds(hours: str | None, minutes: str, seconds: str) -> int:
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds)

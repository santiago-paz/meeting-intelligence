import re
from datetime import date

from pydantic import BaseModel

from app.models import Turn


class TranscriptParseError(ValueError):
    """Raised when no speaker turn can be recognised in the input."""


# One turn per line: "[HH:MM:SS] Speaker: text" or "[MM:SS] Speaker: text".
# The speaker is everything up to the first colon, so colons inside the
# utterance survive.
_TURN_LINE = re.compile(r"^\[(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\]\s+([^:]+):\s*(.*)$")
_DATE_LINE = re.compile(r"^date\s*:\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
_FILENAME_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


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


class TranscriptMetadata(BaseModel):
    title: str | None
    date: date | None


def parse_metadata(raw: str) -> TranscriptMetadata:
    """Title and date from the header lines before the first turn, when present.

    The first plain line is the title; a "Date: YYYY-MM-DD" line is the date.
    Lines with a colon (Attendees: ...) are never mistaken for a title.
    """
    title: str | None = None
    found: date | None = None
    for line in raw.splitlines():
        if _TURN_LINE.match(line):
            break
        stripped = line.strip()
        if not stripped:
            continue
        match = _DATE_LINE.match(stripped)
        if match:
            try:
                found = date.fromisoformat(match.group(1))
            except ValueError:
                found = None
            continue
        if title is None and ":" not in stripped:
            title = stripped
    return TranscriptMetadata(title=title, date=found)


def date_from_filename(filename: str) -> date | None:
    match = _FILENAME_DATE.match(filename)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None

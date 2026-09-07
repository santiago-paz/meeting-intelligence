from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Turn(BaseModel):
    """One speaker turn in a transcript, in the order it was spoken."""

    idx: int
    speaker: str
    start_seconds: int
    text: str


class MeetingCreated(BaseModel):
    id: UUID
    title: str
    turn_count: int
    chunk_count: int


class Chunk(BaseModel):
    """A window of consecutive whole turns, rendered as the text that gets embedded."""

    idx: int
    turn_start: int
    turn_end: int
    text: str
    token_estimate: int
    # Filled by the enrichment step; the chunker leaves them empty.
    context_header: str | None = None
    embedding: list[float] | None = None


class MeetingDetail(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    turns: list[Turn]


class MeetingSummary(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    turn_count: int


class ChunkHit(BaseModel):
    """A chunk returned by similarity search, with where it came from."""

    meeting_id: UUID
    meeting_title: str
    idx: int
    turn_start: int
    turn_end: int
    text: str
    context_header: str | None
    similarity: float

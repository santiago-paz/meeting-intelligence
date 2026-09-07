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

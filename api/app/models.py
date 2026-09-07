from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


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


class Citation(BaseModel):
    """A marker in the answer resolved to the exact moment it points at."""

    ref: str
    meeting_id: UUID
    meeting_title: str
    turn: int
    speaker: str
    start_seconds: int
    timestamp: str


class RetrievedChunk(BaseModel):
    ref: str
    meeting_id: UUID
    meeting_title: str
    turn_start: int
    turn_end: int
    similarity: float


class Trace(BaseModel):
    """Everything about one answered question. Stored, and returned to the caller."""

    mode: str
    question: str
    model: str
    answer: str
    refused: bool
    citations: list[Citation]
    dropped_citations: int
    retrieved: list[RetrievedChunk]
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: float
    latency_ms: int


class AskResponse(Trace):
    trace_id: UUID


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    mode: Literal["classic"] = "classic"
    meeting_id: UUID | None = None
    limit: int = Field(default=8, ge=1, le=20)

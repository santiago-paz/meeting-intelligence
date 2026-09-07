from datetime import date, datetime
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
    decisions: int = 0
    action_items: int = 0
    discarded: int = 0


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
    meeting_date: date | None = None
    turns: list[Turn]
    decisions: list["Decision"] = []
    action_items: list["ActionItem"] = []


class MeetingSummary(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    meeting_date: date | None = None
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
    text: str = ""  # the words at that moment; empty on traces stored before it was recorded


class RetrievedChunk(BaseModel):
    ref: str
    meeting_id: UUID
    meeting_title: str
    turn_start: int
    turn_end: int
    similarity: float | None  # None when fetched by an exact read rather than a search


class ToolCall(BaseModel):
    """One tool invocation in an agentic answer, as recorded in the trace."""

    round: int
    name: str
    input: dict
    summary: str
    latency_ms: int


class MeetingOutline(BaseModel):
    """What the agent sees about a meeting before reading any of it."""

    meeting_id: UUID
    title: str
    meeting_date: date | None
    turn_count: int
    speakers: list[str]
    headers: list[str]


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
    index_rows: int = 0
    tool_calls: list[ToolCall] = []
    rounds: int = 0


class AskResponse(Trace):
    trace_id: UUID


class TraceSummary(BaseModel):
    """One row of the traces page: enough to scan, without the answer text."""

    trace_id: UUID
    created_at: datetime
    mode: str
    question: str
    model: str
    refused: bool
    citation_count: int
    dropped_citations: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cost_usd: float
    latency_ms: int
    rounds: int
    tool_call_count: int


class TraceDetail(Trace):
    """A stored trace, whole, as the traces page shows it."""

    trace_id: UUID
    created_at: datetime


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    mode: Literal["classic", "agentic"] = "classic"
    meeting_id: UUID | None = None
    limit: int = Field(default=8, ge=1, le=20)
    # Whether the extracted decisions and action items go into the prompt.
    # Off by default in classic mode: measured on the same retrieval, the
    # index fixed one aggregation question and cut faithfulness from ~90% to
    # ~65% at 40% more cost. See docs/design.md, Decisions, 2026-09-07.
    use_index: bool = False


class Decision(BaseModel):
    statement: str
    decided_by: str | None
    turn: int
    confidence: float


class ActionItem(BaseModel):
    task: str
    owner: str | None
    due_text: str | None
    due_date: date | None
    status: str
    turn: int
    confidence: float


class IndexRow(BaseModel):
    """One extracted row with where it came from, for the index the model reads."""

    kind: Literal["decision", "action"]
    meeting_id: UUID
    meeting_title: str
    meeting_date: date | None
    turn: int
    text: str
    who: str | None
    due_text: str | None
    due_date: date | None
    status: str | None


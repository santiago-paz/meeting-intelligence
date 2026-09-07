"""Classic mode: the system picks the evidence, the model answers from it.

Embed the question, take the closest chunks, add every extracted decision
and action item as an index, show it all to the model with turns numbered,
check every citation in code, store the trace.
"""

import time
from collections.abc import Iterable
from uuid import UUID

from psycopg import AsyncConnection
from starlette.concurrency import run_in_threadpool

from app.answering import (
    Answerer,
    ChunkContext,
    Citable,
    IndexEntry,
    IndexSection,
    build_prompt,
    validate_citations,
)
from app.embeddings import Embedder
from app.models import AskResponse, ChunkHit, IndexRow, RetrievedChunk, Trace
from app.pricing import cost_usd
from app.repository import get_turns, get_turns_for_meetings, insert_trace, list_index, search_chunks


class AnswerUnavailable(Exception):
    """The model declined to answer (a policy refusal), so there is no answer to check."""


def assign_refs(hits: list[ChunkHit], extra_meeting_ids: Iterable[UUID] = ()) -> dict[UUID, str]:
    """One short ref per meeting, in order of first appearance: M1, M2, ..."""
    refs: dict[UUID, str] = {}
    for meeting_id in [hit.meeting_id for hit in hits] + list(extra_meeting_ids):
        if meeting_id not in refs:
            refs[meeting_id] = f"M{len(refs) + 1}"
    return refs


async def load_contexts(
    conn: AsyncConnection, hits: list[ChunkHit], refs: dict[UUID, str]
) -> list[ChunkContext]:
    contexts = []
    for hit in hits:
        turns = await get_turns(conn, hit.meeting_id, hit.turn_start, hit.turn_end)
        contexts.append(
            ChunkContext(
                ref=refs[hit.meeting_id], meeting_id=hit.meeting_id,
                meeting_title=hit.meeting_title, hit=hit, turns=turns,
            )
        )
    return contexts


def _due(row: IndexRow) -> str | None:
    if row.due_text and row.due_date:
        return f"{row.due_text} ({row.due_date.isoformat()})"
    if row.due_text:
        return row.due_text
    return row.due_date.isoformat() if row.due_date else None


async def build_index(
    conn: AsyncConnection, rows: list[IndexRow], refs: dict[UUID, str]
) -> tuple[list[IndexSection], list[Citable]]:
    """The extracted rows grouped by meeting, plus their turns so citations to them check out."""
    by_meeting: dict[UUID, list[IndexRow]] = {}
    for row in rows:
        by_meeting.setdefault(row.meeting_id, []).append(row)
    turns_by_meeting = await get_turns_for_meetings(conn, list(by_meeting))
    sections, citables = [], []
    for meeting_id, meeting_rows in by_meeting.items():
        first = meeting_rows[0]
        sections.append(
            IndexSection(
                ref=refs[meeting_id], meeting_title=first.meeting_title, meeting_date=first.meeting_date,
                entries=[
                    IndexEntry(kind=r.kind, turn=r.turn, text=r.text, who=r.who, due=_due(r), status=r.status)
                    for r in meeting_rows
                ],
            )
        )
        turn_map = turns_by_meeting.get(meeting_id, {})
        citables.append(
            Citable(
                ref=refs[meeting_id], meeting_id=meeting_id, meeting_title=first.meeting_title,
                turns=[turn_map[r.turn] for r in meeting_rows if r.turn in turn_map],
            )
        )
    return sections, citables


async def answer_classic(
    conn: AsyncConnection,
    *,
    question: str,
    embedder: Embedder,
    answerer: Answerer,
    limit: int = 8,
    meeting_id: UUID | None = None,
    use_index: bool = False,
) -> AskResponse:
    started = time.monotonic()
    query_vector = await run_in_threadpool(embedder.embed_query, question)
    hits = await search_chunks(conn, query_vector, limit=limit, meeting_id=meeting_id)
    index_rows = await list_index(conn) if use_index else []
    refs = assign_refs(hits, [row.meeting_id for row in index_rows])
    contexts = await load_contexts(conn, hits, refs)
    sections, citables = await build_index(conn, index_rows, refs)
    result = await answerer.answer(build_prompt(question, contexts, sections))
    if result.stop_reason == "refusal":
        raise AnswerUnavailable("The model declined to answer this question.")
    check = validate_citations(result.text, [*contexts, *citables])
    trace = Trace(
        mode="classic",
        question=question,
        model=result.model,
        answer=check.answer,
        refused=check.refused,
        citations=check.citations,
        dropped_citations=check.dropped,
        retrieved=[
            RetrievedChunk(
                ref=c.ref, meeting_id=c.hit.meeting_id, meeting_title=c.hit.meeting_title,
                turn_start=c.hit.turn_start, turn_end=c.hit.turn_end, similarity=c.hit.similarity,
            )
            for c in contexts
        ],
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cache_read_tokens=result.cache_read_tokens,
        cache_write_tokens=result.cache_write_tokens,
        cost_usd=cost_usd(
            result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cache_read_tokens=result.cache_read_tokens,
            cache_write_tokens=result.cache_write_tokens,
        ),
        latency_ms=int((time.monotonic() - started) * 1000),
        index_rows=len(index_rows),
    )
    trace_id = await insert_trace(conn, trace)
    return AskResponse(**trace.model_dump(), trace_id=trace_id)

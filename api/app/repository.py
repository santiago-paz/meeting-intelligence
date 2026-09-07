"""Persistence for meetings, turns and chunks. Plain SQL over psycopg."""

from datetime import date
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.models import (
    ActionItem,
    Chunk,
    ChunkHit,
    Decision,
    IndexRow,
    MeetingDetail,
    MeetingOutline,
    MeetingSummary,
    Trace,
    TraceDetail,
    TraceSummary,
    Turn,
)


async def insert_meeting(
    conn: AsyncConnection,
    *,
    title: str,
    source_filename: str,
    turns: list[Turn],
    chunks: list[Chunk],
    meeting_date: date | None = None,
) -> UUID:
    """Store a meeting with its turns and chunks in one transaction; return its id."""
    async with conn.transaction():
        cur = await conn.execute(
            "INSERT INTO meetings (title, source_filename, meeting_date) VALUES (%s, %s, %s)"
            " RETURNING id",
            (title, source_filename, meeting_date),
        )
        meeting_id: UUID = (await cur.fetchone())[0]
        async with conn.cursor() as batch:
            await batch.executemany(
                "INSERT INTO turns (meeting_id, idx, speaker, start_seconds, text)"
                " VALUES (%s, %s, %s, %s, %s)",
                [(meeting_id, t.idx, t.speaker, t.start_seconds, t.text) for t in turns],
            )
            await batch.executemany(
                "INSERT INTO chunks (meeting_id, idx, turn_start, turn_end, text,"
                " token_estimate, context_header, embedding)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)",
                [
                    (
                        meeting_id, c.idx, c.turn_start, c.turn_end, c.text,
                        c.token_estimate, c.context_header, _to_pgvector(c.embedding),
                    )
                    for c in chunks
                ],
            )
    return meeting_id


async def get_meeting(conn: AsyncConnection, meeting_id: UUID) -> MeetingDetail | None:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT id, title, created_at, meeting_date FROM meetings WHERE id = %s", (meeting_id,)
        )
        row = await cur.fetchone()
        if row is None:
            return None
        await cur.execute(
            "SELECT idx, speaker, start_seconds, text FROM turns"
            " WHERE meeting_id = %s ORDER BY idx",
            (meeting_id,),
        )
        turns = [Turn(**r) for r in await cur.fetchall()]
        await cur.execute(
            "SELECT statement, decided_by, turn_idx AS turn, confidence FROM decisions"
            " WHERE meeting_id = %s ORDER BY turn_idx, id",
            (meeting_id,),
        )
        decisions = [Decision(**r) for r in await cur.fetchall()]
        await cur.execute(
            "SELECT task, owner, due_text, due_date, status, turn_idx AS turn, confidence"
            " FROM action_items WHERE meeting_id = %s ORDER BY turn_idx, id",
            (meeting_id,),
        )
        action_items = [ActionItem(**r) for r in await cur.fetchall()]
    return MeetingDetail(**row, turns=turns, decisions=decisions, action_items=action_items)


async def list_meetings(conn: AsyncConnection) -> list[MeetingSummary]:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT m.id, m.title, m.created_at, m.meeting_date, count(t.idx) AS turn_count"
            " FROM meetings m LEFT JOIN turns t ON t.meeting_id = m.id"
            " GROUP BY m.id ORDER BY m.created_at DESC, m.id"
        )
        return [MeetingSummary(**r) for r in await cur.fetchall()]


async def search_chunks(
    conn: AsyncConnection,
    query_embedding: list[float],
    *,
    limit: int = 8,
    meeting_id: UUID | None = None,
) -> list[ChunkHit]:
    """Chunks closest to the query by cosine similarity, most similar first."""
    vector = _to_pgvector(query_embedding)
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT c.meeting_id, m.title AS meeting_title, c.idx, c.turn_start, c.turn_end,"
            " c.text, c.context_header, 1 - (c.embedding <=> %s::vector) AS similarity"
            " FROM chunks c JOIN meetings m ON m.id = c.meeting_id"
            " WHERE c.embedding IS NOT NULL"
            " AND (%s::uuid IS NULL OR c.meeting_id = %s)"
            " ORDER BY c.embedding <=> %s::vector"
            " LIMIT %s",
            (vector, meeting_id, meeting_id, vector, limit),
        )
        return [ChunkHit(**row) for row in await cur.fetchall()]


def _to_pgvector(embedding: list[float] | None) -> str | None:
    """pgvector's text form, so no adapter registration is needed on the pool."""
    if embedding is None:
        return None
    return "[" + ",".join(repr(float(x)) for x in embedding) + "]"


async def get_turns(conn: AsyncConnection, meeting_id: UUID, start: int, end: int) -> list[Turn]:
    """Turns start..end inclusive, in order."""
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT idx, speaker, start_seconds, text FROM turns"
            " WHERE meeting_id = %s AND idx BETWEEN %s AND %s ORDER BY idx",
            (meeting_id, start, end),
        )
        return [Turn(**row) for row in await cur.fetchall()]


async def insert_trace(conn: AsyncConnection, trace: Trace) -> UUID:
    async with conn.transaction():
        return await _insert_trace(conn, trace)


async def _insert_trace(conn: AsyncConnection, trace: Trace) -> UUID:
    cur = await conn.execute(
        "INSERT INTO traces (mode, question, model, answer, refused, citations,"
        " dropped_citations, retrieved, input_tokens, output_tokens, cache_read_tokens,"
        " cache_write_tokens, cost_usd, latency_ms, index_rows, tool_calls, rounds)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (
            trace.mode, trace.question, trace.model, trace.answer, trace.refused,
            Jsonb([c.model_dump(mode="json") for c in trace.citations]),
            trace.dropped_citations,
            Jsonb([r.model_dump(mode="json") for r in trace.retrieved]),
            trace.input_tokens, trace.output_tokens, trace.cache_read_tokens,
            trace.cache_write_tokens, trace.cost_usd, trace.latency_ms, trace.index_rows,
            Jsonb([c.model_dump(mode="json") for c in trace.tool_calls]), trace.rounds,
        ),
    )
    return (await cur.fetchone())[0]


async def insert_extraction(
    conn: AsyncConnection, meeting_id: UUID, decisions: list[Decision], action_items: list[ActionItem]
) -> None:
    async with conn.transaction(), conn.cursor() as batch:
        await batch.executemany(
            "INSERT INTO decisions (meeting_id, statement, decided_by, turn_idx, confidence)"
            " VALUES (%s, %s, %s, %s, %s)",
            [(meeting_id, d.statement, d.decided_by, d.turn, d.confidence) for d in decisions],
        )
        await batch.executemany(
            "INSERT INTO action_items (meeting_id, task, owner, due_text, due_date, status,"
            " turn_idx, confidence) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            [
                (meeting_id, a.task, a.owner, a.due_text, a.due_date, a.status, a.turn, a.confidence)
                for a in action_items
            ],
        )


async def list_index(conn: AsyncConnection) -> list[IndexRow]:
    """Every extracted row across meetings, oldest meeting first, in turn order."""
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT 'decision' AS kind, m.id AS meeting_id, m.title AS meeting_title,"
            " m.meeting_date, d.turn_idx AS turn, d.statement AS text, d.decided_by AS who,"
            " NULL AS due_text, NULL::date AS due_date, NULL AS status"
            " FROM decisions d JOIN meetings m ON m.id = d.meeting_id"
            " UNION ALL"
            " SELECT 'action', m.id, m.title, m.meeting_date, a.turn_idx, a.task, a.owner,"
            " a.due_text, a.due_date, a.status"
            " FROM action_items a JOIN meetings m ON m.id = a.meeting_id"
            " ORDER BY meeting_date NULLS LAST, meeting_title, turn, kind"
        )
        return [IndexRow(**row) for row in await cur.fetchall()]


async def get_turns_for_meetings(
    conn: AsyncConnection, meeting_ids: list[UUID]
) -> dict[UUID, dict[int, Turn]]:
    result: dict[UUID, dict[int, Turn]] = {}
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT meeting_id, idx, speaker, start_seconds, text FROM turns"
            " WHERE meeting_id = ANY(%s) ORDER BY meeting_id, idx",
            (meeting_ids,),
        )
        for row in await cur.fetchall():
            meeting_id = row.pop("meeting_id")
            result.setdefault(meeting_id, {})[row["idx"]] = Turn(**row)
    return result


async def list_meeting_outlines(conn: AsyncConnection) -> list[MeetingOutline]:
    """Each meeting as the agent first sees it: date, speakers, size, chunk headers."""
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT m.id AS meeting_id, m.title, m.meeting_date,"
            " (SELECT count(*) FROM turns t WHERE t.meeting_id = m.id) AS turn_count,"
            " (SELECT coalesce(array_agg(DISTINCT t.speaker ORDER BY t.speaker), '{}')"
            "  FROM turns t WHERE t.meeting_id = m.id) AS speakers,"
            " (SELECT coalesce(array_agg(c.context_header ORDER BY c.idx), '{}')"
            "  FROM chunks c WHERE c.meeting_id = m.id AND c.context_header IS NOT NULL) AS headers"
            " FROM meetings m ORDER BY m.meeting_date NULLS LAST, m.title"
        )
        return [MeetingOutline(**row) for row in await cur.fetchall()]


_TRACE_COLUMNS = (
    "id AS trace_id, created_at, mode, question, model, answer, refused, citations, dropped_citations,"
    " retrieved, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, cost_usd::float AS cost_usd,"
    " latency_ms, index_rows, tool_calls, rounds"
)


async def list_traces(conn: AsyncConnection, *, limit: int = 50) -> list[TraceSummary]:
    """Newest first. Counts stand in for the JSON columns so the list stays light."""
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT id AS trace_id, created_at, mode, question, model, refused,"
            " jsonb_array_length(citations) AS citation_count, dropped_citations,"
            " input_tokens, output_tokens, cache_read_tokens, cost_usd::float AS cost_usd, latency_ms,"
            " rounds, jsonb_array_length(tool_calls) AS tool_call_count"
            " FROM traces ORDER BY created_at DESC, id LIMIT %s",
            (limit,),
        )
        return [TraceSummary(**r) for r in await cur.fetchall()]


async def get_trace(conn: AsyncConnection, trace_id: UUID) -> TraceDetail | None:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(f"SELECT {_TRACE_COLUMNS} FROM traces WHERE id = %s", (trace_id,))
        row = await cur.fetchone()
    return TraceDetail(**row) if row else None

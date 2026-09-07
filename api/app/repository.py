"""Persistence for meetings, turns and chunks. Plain SQL over psycopg."""

from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.models import Chunk, ChunkHit, MeetingDetail, MeetingSummary, Trace, Turn


async def insert_meeting(
    conn: AsyncConnection,
    *,
    title: str,
    source_filename: str,
    turns: list[Turn],
    chunks: list[Chunk],
) -> UUID:
    """Store a meeting with its turns and chunks in one transaction; return its id."""
    async with conn.transaction():
        cur = await conn.execute(
            "INSERT INTO meetings (title, source_filename) VALUES (%s, %s) RETURNING id",
            (title, source_filename),
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
            "SELECT id, title, created_at FROM meetings WHERE id = %s", (meeting_id,)
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
    return MeetingDetail(**row, turns=turns)


async def list_meetings(conn: AsyncConnection) -> list[MeetingSummary]:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT m.id, m.title, m.created_at, count(t.idx) AS turn_count"
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
        " cache_write_tokens, cost_usd, latency_ms)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (
            trace.mode, trace.question, trace.model, trace.answer, trace.refused,
            Jsonb([c.model_dump(mode="json") for c in trace.citations]),
            trace.dropped_citations,
            Jsonb([r.model_dump(mode="json") for r in trace.retrieved]),
            trace.input_tokens, trace.output_tokens, trace.cache_read_tokens,
            trace.cache_write_tokens, trace.cost_usd, trace.latency_ms,
        ),
    )
    return (await cur.fetchone())[0]

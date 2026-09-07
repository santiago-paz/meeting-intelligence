"""Classic mode: the system picks the evidence, the model answers from it.

Embed the question, take the closest chunks, add every extracted decision
and action item as an index, show it all to the model with turns numbered,
check every citation in code, store the trace.
"""

import time
from collections.abc import Awaitable, Callable, Iterable
from uuid import UUID

from psycopg import AsyncConnection
from starlette.concurrency import run_in_threadpool

from app.agentic import DEFAULT_MAX_ROUNDS, SYSTEM_RULES, Agent, ToolError, render_index
from app.answering import (
    Answerer,
    ChunkContext,
    Citable,
    IndexEntry,
    IndexSection,
    build_prompt,
    validate_citations,
)
from app.chunking import render_numbered_turns
from app.embeddings import Embedder
from app.models import AskResponse, ChunkHit, IndexRow, RetrievedChunk, ToolCall, Trace
from app.pricing import cost_usd
from app.repository import (
    get_turns,
    get_turns_for_meetings,
    insert_trace,
    list_index,
    list_meeting_outlines,
    search_chunks,
)


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


MAX_READ_TURNS = 40


async def answer_agentic(
    conn: AsyncConnection,
    *,
    question: str,
    embedder: Embedder,
    agent: Agent,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    on_tool_call: Callable[[ToolCall], Awaitable[None]] | None = None,
) -> AskResponse:
    """Agentic mode: the model reads the table of contents, then fetches what it needs.

    Every tool result becomes citable; nothing else does. The index block is
    stable between questions, so it carries the cache marker.
    """
    started = time.monotonic()
    outlines = await list_meeting_outlines(conn)
    rows = await list_index(conn)
    refs = {outline.meeting_id: f"M{i + 1}" for i, outline in enumerate(outlines)}
    by_ref = {refs[outline.meeting_id]: outline for outline in outlines}
    system = [
        {"type": "text", "text": SYSTEM_RULES},
        {"type": "text", "text": render_index(outlines, rows, refs), "cache_control": {"type": "ephemeral"}},
    ]
    citables: list[Citable] = []
    retrieved: list[RetrievedChunk] = []

    async def execute_tool(name: str, inputs: dict) -> tuple[str, str]:
        if name == "search_transcripts":
            ref = inputs.get("meeting_ref")
            if ref is not None and ref not in by_ref:
                raise ToolError(f"unknown meeting ref {ref}")
            vector = await run_in_threadpool(embedder.embed_query, inputs["query"])
            hits = await search_chunks(
                conn, vector, limit=5, meeting_id=by_ref[ref].meeting_id if ref else None
            )
            parts = []
            for hit in hits:
                turns = await get_turns(conn, hit.meeting_id, hit.turn_start, hit.turn_end)
                hit_ref = refs[hit.meeting_id]
                citables.append(Citable(ref=hit_ref, meeting_id=hit.meeting_id, meeting_title=hit.meeting_title, turns=turns))
                retrieved.append(RetrievedChunk(
                    ref=hit_ref, meeting_id=hit.meeting_id, meeting_title=hit.meeting_title,
                    turn_start=hit.turn_start, turn_end=hit.turn_end, similarity=hit.similarity,
                ))
                parts.append(
                    f'<excerpt ref="{hit_ref}" meeting="{hit.meeting_title}"'
                    f' turns="{hit.turn_start}-{hit.turn_end}" similarity="{hit.similarity:.2f}">'
                )
                if hit.context_header:
                    parts.append(f"About: {hit.context_header}")
                parts.append(render_numbered_turns(turns))
                parts.append("</excerpt>")
            return "\n".join(parts) or "No excerpts found.", f"{len(hits)} excerpt(s) for {inputs['query']!r}"
        if name == "read_turns":
            ref = inputs.get("meeting_ref")
            outline = by_ref.get(ref)
            if outline is None:
                raise ToolError(f"unknown meeting ref {ref}")
            start, end = int(inputs["start"]), int(inputs["end"])
            if start < 0 or start > end:
                raise ToolError("start must be at least 0 and not after end")
            end = min(end, start + MAX_READ_TURNS - 1, max(outline.turn_count - 1, 0))
            turns = await get_turns(conn, outline.meeting_id, start, end)
            if not turns:
                raise ToolError(f"{ref} has no turns in {start}-{end}; it has turns 0-{outline.turn_count - 1}")
            first, last = turns[0].idx, turns[-1].idx
            citables.append(Citable(ref=ref, meeting_id=outline.meeting_id, meeting_title=outline.title, turns=turns))
            retrieved.append(RetrievedChunk(
                ref=ref, meeting_id=outline.meeting_id, meeting_title=outline.title,
                turn_start=first, turn_end=last, similarity=None,
            ))
            text = f'<excerpt ref="{ref}" meeting="{outline.title}" turns="{first}-{last}">\n{render_numbered_turns(turns)}\n</excerpt>'
            return text, f"{ref} turns {first}-{last}"
        raise ToolError(f"unknown tool {name}")

    run = await agent.run(
        system=system, question=question, execute_tool=execute_tool,
        max_rounds=max_rounds, on_tool_call=on_tool_call,
    )
    if run.stop_reason == "refusal":
        raise AnswerUnavailable("The model declined to answer this question.")
    check = validate_citations(run.text, citables)
    trace = Trace(
        mode="agentic",
        question=question,
        model=run.model,
        answer=check.answer,
        refused=check.refused,
        citations=check.citations,
        dropped_citations=check.dropped,
        retrieved=retrieved,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        cache_read_tokens=run.cache_read_tokens,
        cache_write_tokens=run.cache_write_tokens,
        cost_usd=cost_usd(
            run.model,
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            cache_read_tokens=run.cache_read_tokens,
            cache_write_tokens=run.cache_write_tokens,
        ),
        latency_ms=int((time.monotonic() - started) * 1000),
        index_rows=len(rows),
        tool_calls=run.tool_calls,
        rounds=run.rounds,
    )
    trace_id = await insert_trace(conn, trace)
    return AskResponse(**trace.model_dump(), trace_id=trace_id)

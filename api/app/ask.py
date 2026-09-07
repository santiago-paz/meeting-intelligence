"""Classic mode: the system picks the evidence, the model answers from it.

Embed the question, take the closest chunks, show them to the model with
their turns numbered, check every citation in code, store the trace.
"""

import time
from uuid import UUID

from psycopg import AsyncConnection
from starlette.concurrency import run_in_threadpool

from app.answering import Answerer, ChunkContext, build_prompt, validate_citations
from app.embeddings import Embedder
from app.models import AskResponse, ChunkHit, RetrievedChunk, Trace
from app.pricing import cost_usd
from app.repository import get_turns, insert_trace, search_chunks


class AnswerUnavailable(Exception):
    """The model declined to answer (a policy refusal), so there is no answer to check."""


def assign_refs(hits: list[ChunkHit]) -> dict[UUID, str]:
    """One short ref per meeting, in order of first appearance: M1, M2, ..."""
    refs: dict[UUID, str] = {}
    for hit in hits:
        if hit.meeting_id not in refs:
            refs[hit.meeting_id] = f"M{len(refs) + 1}"
    return refs


async def load_contexts(conn: AsyncConnection, hits: list[ChunkHit]) -> list[ChunkContext]:
    refs = assign_refs(hits)
    contexts = []
    for hit in hits:
        turns = await get_turns(conn, hit.meeting_id, hit.turn_start, hit.turn_end)
        contexts.append(ChunkContext(ref=refs[hit.meeting_id], hit=hit, turns=turns))
    return contexts


async def answer_classic(
    conn: AsyncConnection,
    *,
    question: str,
    embedder: Embedder,
    answerer: Answerer,
    limit: int = 8,
    meeting_id: UUID | None = None,
) -> AskResponse:
    started = time.monotonic()
    query_vector = await run_in_threadpool(embedder.embed_query, question)
    hits = await search_chunks(conn, query_vector, limit=limit, meeting_id=meeting_id)
    contexts = await load_contexts(conn, hits)
    result = await answerer.answer(build_prompt(question, contexts))
    if result.stop_reason == "refusal":
        raise AnswerUnavailable("The model declined to answer this question.")
    check = validate_citations(result.text, contexts)
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
                ref=c.ref,
                meeting_id=c.hit.meeting_id,
                meeting_title=c.hit.meeting_title,
                turn_start=c.hit.turn_start,
                turn_end=c.hit.turn_end,
                similarity=c.hit.similarity,
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
    )
    trace_id = await insert_trace(conn, trace)
    return AskResponse(**trace.model_dump(), trace_id=trace_id)

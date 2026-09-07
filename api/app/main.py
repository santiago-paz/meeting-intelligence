import asyncio
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated, AsyncIterator
from uuid import UUID

from anthropic import AsyncAnthropic
from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool
from starlette.concurrency import run_in_threadpool

from app.answering import Answerer, ClaudeAnswerer
from app.ask import AnswerUnavailable, answer_classic
from app.chunking import build_chunks, render_numbered_turns
from app.db import migrate
from app.embeddings import Embedder, FastEmbedEmbedder
from app.enrichment import ClaudeEnricher, Enricher
from app.extraction import ClaudeExtractor, Extractor, validate_extraction
from app.models import AskRequest, AskResponse, MeetingCreated, MeetingDetail, MeetingSummary
from app.parsing import TranscriptParseError, date_from_filename, parse_metadata, parse_transcript
from app.repository import get_meeting, insert_extraction, insert_meeting, list_meetings
from app.settings import Settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    pool = AsyncConnectionPool(settings.database_url, open=False)
    await pool.open(wait=True, timeout=10)
    async with pool.connection() as conn:
        await migrate(conn)
    app.state.settings = settings
    app.state.pool = pool
    app.state.enricher = None
    app.state.answerer = None
    app.state.extractor = None
    if settings.anthropic_api_key:
        claude = AsyncAnthropic(api_key=settings.anthropic_api_key, base_url=settings.claude_base_url)
        app.state.enricher = ClaudeEnricher(claude, model=settings.context_header_model)
        app.state.answerer = ClaudeAnswerer(
            claude, model=settings.answer_model, effort=settings.answer_effort
        )
        app.state.extractor = ClaudeExtractor(claude, model=settings.extraction_model)
    yield
    await pool.close()


app = FastAPI(title="Meeting Intelligence API", lifespan=lifespan)


async def get_conn(request: Request) -> AsyncIterator[AsyncConnection]:
    async with request.app.state.pool.connection() as conn:
        yield conn


def get_enricher(request: Request) -> Enricher:
    enricher = request.app.state.enricher
    if enricher is None:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not set; ingest needs it to write context headers.",
        )
    return enricher


def get_extractor(request: Request) -> Extractor:
    extractor = request.app.state.extractor
    if extractor is None:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not set; ingest needs it to extract decisions.",
        )
    return extractor


def get_answerer(request: Request) -> Answerer:
    answerer = request.app.state.answerer
    if answerer is None:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not set; answering needs it.",
        )
    return answerer


@lru_cache(maxsize=1)
def _load_embedder(model_name: str) -> FastEmbedEmbedder:
    return FastEmbedEmbedder(model_name)


def get_embedder(request: Request) -> Embedder:
    # Loaded on first use, not at startup: tests never touch the real model,
    # and the first upload pays the load (and, once, the download).
    return _load_embedder(request.app.state.settings.embedding_model)


Conn = Annotated[AsyncConnection, Depends(get_conn)]
EnricherDep = Annotated[Enricher, Depends(get_enricher)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
AnswererDep = Annotated[Answerer, Depends(get_answerer)]
ExtractorDep = Annotated[Extractor, Depends(get_extractor)]


@app.post("/meetings", response_model=MeetingCreated)
async def create_meeting(
    file: UploadFile, conn: Conn, enricher: EnricherDep, embedder: EmbedderDep, extractor: ExtractorDep
) -> MeetingCreated:
    """Ingest a transcript: parse it into turns, cut chunks, write a context
    header per chunk and extract decisions and action items (the two model
    passes run concurrently), embed header plus chunk, check the extracted
    rows in code, store everything atomically."""
    try:
        raw = (await file.read()).decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="File must be UTF-8 encoded text.") from exc
    try:
        turns = parse_transcript(raw)
    except TranscriptParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    filename = file.filename or "meeting"
    title = Path(filename).stem
    meeting_date = parse_metadata(raw).date or date_from_filename(filename)
    chunks = build_chunks(turns)
    headers, extraction = await asyncio.gather(
        enricher.context_headers(raw, chunks),
        extractor.extract(render_numbered_turns(turns), meeting_date),
    )
    vectors = await run_in_threadpool(
        embedder.embed_documents,
        [f"{header}\n\n{chunk.text}" for header, chunk in zip(headers, chunks)],
    )
    enriched = [
        chunk.model_copy(update={"context_header": header, "embedding": vector})
        for chunk, header, vector in zip(chunks, headers, vectors)
    ]
    decisions, action_items, discarded = validate_extraction(extraction, turns, meeting_date)
    async with conn.transaction():
        meeting_id = await insert_meeting(
            conn, title=title, source_filename=filename, turns=turns, chunks=enriched,
            meeting_date=meeting_date,
        )
        await insert_extraction(conn, meeting_id, decisions, action_items)
    return MeetingCreated(
        id=meeting_id, title=title, turn_count=len(turns), chunk_count=len(chunks),
        decisions=len(decisions), action_items=len(action_items), discarded=discarded,
    )


@app.get("/meetings", response_model=list[MeetingSummary])
async def read_meetings(conn: Conn) -> list[MeetingSummary]:
    return await list_meetings(conn)


@app.get("/meetings/{meeting_id}", response_model=MeetingDetail)
async def read_meeting(meeting_id: UUID, conn: Conn) -> MeetingDetail:
    meeting = await get_meeting(conn, meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found.")
    return meeting


@app.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest, conn: Conn, answerer: AnswererDep, embedder: EmbedderDep) -> AskResponse:
    """Answer a question from the meetings. Classic mode: the system retrieves
    the closest chunks, the model answers from them with inline citations, and
    every citation is checked against what the model was shown."""
    try:
        return await answer_classic(
            conn,
            question=body.question,
            embedder=embedder,
            answerer=answerer,
            limit=body.limit,
            meeting_id=body.meeting_id,
            use_index=body.use_index,
        )
    except AnswerUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

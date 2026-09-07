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

from app.chunking import build_chunks
from app.db import migrate
from app.embeddings import Embedder, FastEmbedEmbedder
from app.enrichment import ClaudeEnricher, Enricher
from app.models import MeetingCreated, MeetingDetail, MeetingSummary
from app.parsing import TranscriptParseError, parse_transcript
from app.repository import get_meeting, insert_meeting, list_meetings
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
    app.state.enricher = (
        ClaudeEnricher(
            AsyncAnthropic(api_key=settings.anthropic_api_key, base_url=settings.claude_base_url),
            model=settings.context_header_model,
        )
        if settings.anthropic_api_key
        else None
    )
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


@app.post("/meetings", response_model=MeetingCreated)
async def create_meeting(
    file: UploadFile, conn: Conn, enricher: EnricherDep, embedder: EmbedderDep
) -> MeetingCreated:
    """Ingest a transcript: parse it into turns, cut chunks, write a context
    header for each chunk, embed header plus chunk, store everything.
    Extraction of decisions and action items joins this pipeline next."""
    try:
        raw = (await file.read()).decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="File must be UTF-8 encoded text.") from exc
    try:
        turns = parse_transcript(raw)
    except TranscriptParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    chunks = build_chunks(turns)
    headers = await enricher.context_headers(raw, chunks)
    vectors = await run_in_threadpool(
        embedder.embed_documents,
        [f"{header}\n\n{chunk.text}" for header, chunk in zip(headers, chunks)],
    )
    enriched = [
        chunk.model_copy(update={"context_header": header, "embedding": vector})
        for chunk, header, vector in zip(chunks, headers, vectors)
    ]
    filename = file.filename or "meeting"
    title = Path(filename).stem
    meeting_id = await insert_meeting(
        conn, title=title, source_filename=filename, turns=turns, chunks=enriched
    )
    return MeetingCreated(
        id=meeting_id, title=title, turn_count=len(turns), chunk_count=len(chunks)
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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

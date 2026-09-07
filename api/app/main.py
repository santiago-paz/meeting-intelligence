from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, AsyncIterator
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from app.chunking import build_chunks
from app.db import migrate
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
    app.state.pool = pool
    yield
    await pool.close()


app = FastAPI(title="Meeting Intelligence API", lifespan=lifespan)


async def get_conn(request: Request) -> AsyncIterator[AsyncConnection]:
    async with request.app.state.pool.connection() as conn:
        yield conn


Conn = Annotated[AsyncConnection, Depends(get_conn)]


@app.post("/meetings", response_model=MeetingCreated)
async def create_meeting(file: UploadFile, conn: Conn) -> MeetingCreated:
    """Ingest a transcript: parse it into turns, cut chunks, store everything.
    Context headers, embeddings and extraction join this pipeline step by step."""
    try:
        raw = (await file.read()).decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="File must be UTF-8 encoded text.") from exc
    try:
        turns = parse_transcript(raw)
    except TranscriptParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    chunks = build_chunks(turns)
    filename = file.filename or "meeting"
    title = Path(filename).stem
    meeting_id = await insert_meeting(
        conn, title=title, source_filename=filename, turns=turns, chunks=chunks
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

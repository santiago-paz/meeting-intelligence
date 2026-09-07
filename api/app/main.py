import asyncio
import json
import logging
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated, AsyncIterator
from uuid import UUID

from anthropic import AsyncAnthropic
from fastapi import Depends, FastAPI, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool
from starlette.concurrency import run_in_threadpool

from app.agentic import Agent, ClaudeAgent
from app.answering import Answerer, ClaudeAnswerer
from app.ask import AnswerUnavailable, answer_agentic, answer_classic
from app.chunking import build_chunks, render_numbered_turns
from app.db import migrate
from app.embeddings import Embedder, FastEmbedEmbedder
from app.enrichment import ClaudeEnricher, Enricher
from app.extraction import ClaudeExtractor, Extractor, validate_extraction
from app.models import (
    AskRequest,
    AskResponse,
    MeetingCreated,
    MeetingDetail,
    MeetingSummary,
    SampleStatus,
    SamplesLoaded,
    TestModeStatus,
    ToolCall,
    TraceDetail,
    TraceSummary,
)
from app.parsing import TranscriptParseError, date_from_filename, parse_metadata, parse_transcript
from app.recorded import (
    RecordedAgent,
    RecordedAnswerer,
    RecordedEnricher,
    RecordedExtractor,
    Recording,
    StaleRecording,
    load_recording,
)
from app.repository import (
    existing_titles,
    get_meeting,
    get_trace,
    insert_extraction,
    insert_meeting,
    list_meetings,
    list_traces,
)
from app.settings import Settings

log = logging.getLogger(__name__)
SAMPLES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "transcripts"


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
    app.state.agent = None
    if settings.anthropic_api_key:
        claude = AsyncAnthropic(api_key=settings.anthropic_api_key, base_url=settings.claude_base_url)
        app.state.enricher = ClaudeEnricher(claude, model=settings.context_header_model)
        app.state.answerer = ClaudeAnswerer(
            claude, model=settings.answer_model, effort=settings.answer_effort
        )
        app.state.extractor = ClaudeExtractor(claude, model=settings.extraction_model)
        app.state.agent = ClaudeAgent(claude, model=settings.answer_model, effort=settings.answer_effort)
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


def get_agent(request: Request) -> Agent | None:
    """None when no key is configured; the endpoint turns that into a 503 for the mode that needs it."""
    return request.app.state.agent


def get_answerer(request: Request) -> Answerer | None:
    return request.app.state.answerer


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
AnswererDep = Annotated[Answerer | None, Depends(get_answerer)]
ExtractorDep = Annotated[Extractor, Depends(get_extractor)]
AgentDep = Annotated[Agent | None, Depends(get_agent)]


async def ingest_transcript(
    conn: AsyncConnection, raw: str, filename: str, *, enricher: Enricher, embedder: Embedder, extractor: Extractor
) -> MeetingCreated:
    """Parse a transcript into turns, cut chunks, write a context header per
    chunk and extract decisions and action items (the two model passes run
    concurrently), embed header plus chunk, check the extracted rows in code,
    store everything atomically."""
    try:
        turns = parse_transcript(raw)
    except TranscriptParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
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


@app.post("/meetings", response_model=MeetingCreated)
async def create_meeting(
    file: UploadFile, conn: Conn, enricher: EnricherDep, embedder: EmbedderDep, extractor: ExtractorDep
) -> MeetingCreated:
    """Ingest an uploaded transcript; see ingest_transcript."""
    try:
        raw = (await file.read()).decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="File must be UTF-8 encoded text.") from exc
    return await ingest_transcript(
        conn, raw, file.filename or "meeting", enricher=enricher, embedder=embedder, extractor=extractor
    )


def _recording() -> Recording:
    try:
        return load_recording()
    except StaleRecording as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def _sample_status(conn: AsyncConnection, recording: Recording) -> SampleStatus:
    titles = sorted(recording.meetings)
    present = await existing_titles(conn, titles)
    return SampleStatus(loaded=[t for t in titles if t in present], missing=[t for t in titles if t not in present])


@app.post("/meetings/samples", response_model=SamplesLoaded)
async def load_samples(conn: Conn, embedder: EmbedderDep) -> SamplesLoaded:
    """Ingest the sample transcripts with the context headers and extracted
    rows of the recorded run, so the corpus is there without a key and
    without spending one. Embedding is local and runs for real. A title that
    is already stored is skipped, so this can be called again safely."""
    recording = _recording()
    status = await _sample_status(conn, recording)
    loaded: list[MeetingCreated] = []
    for title in status.missing:
        raw = (SAMPLES_DIR / f"{title}.txt").read_text(encoding="utf-8-sig")
        meeting = recording.meetings[title]
        try:
            loaded.append(await ingest_transcript(
                conn, raw, f"{title}.txt",
                enricher=RecordedEnricher(meeting), embedder=embedder, extractor=RecordedExtractor(meeting),
            ))
        except StaleRecording as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        # One transaction per sample: each keeps its own timestamp (so the list has an order),
        # and a failure part-way leaves the ones already in, which a retry then skips.
        await conn.commit()
    return SamplesLoaded(loaded=loaded, skipped=status.loaded)


@app.get("/test-mode", response_model=TestModeStatus)
async def read_test_mode(conn: Conn, answerer: AnswererDep) -> TestModeStatus:
    """What test mode can offer right now. The UI turns it on by default when there is no key."""
    recording = _recording()
    return TestModeStatus(
        has_key=answerer is not None, samples=await _sample_status(conn, recording), questions=recording.questions()
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
async def ask(
    body: AskRequest, conn: Conn, embedder: EmbedderDep, answerer: AnswererDep, agent: AgentDep, request: Request
) -> AskResponse:
    """Answer a question from the meetings.

    Classic mode: the system retrieves the closest chunks and the model answers
    from them. Agentic mode: the model reads a table of contents and fetches
    what it needs with tools. Both cite inline, and every citation is checked
    against what the model was actually shown."""
    service = await _service_for(body, conn, answerer, agent)
    try:
        if body.mode == "agentic":
            return await answer_agentic(
                conn,
                question=body.question,
                embedder=embedder,
                agent=service,
                max_rounds=request.app.state.settings.agent_max_rounds,
            )
        return await answer_classic(
            conn,
            question=body.question,
            embedder=embedder,
            answerer=service,
            limit=body.limit,
            meeting_id=body.meeting_id,
            use_index=body.use_index,
        )
    except AnswerUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


async def _service_for(body: AskRequest, conn: AsyncConnection, answerer: Answerer | None, agent: Agent | None):
    """The answerer or agent a question runs on. In test mode it is the recorded
    run replayed, which knows only the sample questions and needs the sample
    meetings in place; otherwise the configured one, if a key gave us one."""
    if body.test_mode:
        recording = _recording()
        recorded = recording.find(body.question, body.mode)
        if recorded is None:
            raise HTTPException(
                status_code=422, detail="Test mode answers only the sample questions. Pick one of them."
            )
        if (await _sample_status(conn, recording)).missing:
            raise HTTPException(
                status_code=409, detail="The sample meetings are not loaded yet. Load them on the Meetings page first."
            )
        return RecordedAgent(recorded) if body.mode == "agentic" else RecordedAnswerer(recorded)
    service = agent if body.mode == "agentic" else answerer
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not set; answering needs it. Test mode answers the sample questions without a key.",
        )
    return service


def _event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


@app.post("/ask/stream")
async def ask_stream(
    body: AskRequest, conn: Conn, embedder: EmbedderDep, answerer: AnswererDep, agent: AgentDep, request: Request
) -> StreamingResponse:
    """The same answer as /ask, as server-sent events.

    Agentic mode sends a `tool_call` event for every tool the model uses, as
    it happens, so the wait reads as work; both modes end with one `answer`
    event carrying the /ask payload, or an `error` event with a detail. The
    stream takes its own connection from the pool: a request-scoped one may
    be returned before the last event is written."""
    service = await _service_for(body, conn, answerer, agent)
    queue: asyncio.Queue[tuple[str, dict] | None] = asyncio.Queue()

    async def on_tool_call(call: ToolCall) -> None:
        await queue.put(("tool_call", call.model_dump(mode="json")))

    async def work() -> None:
        try:
            async with request.app.state.pool.connection() as conn:
                if body.mode == "agentic":
                    response = await answer_agentic(
                        conn,
                        question=body.question,
                        embedder=embedder,
                        agent=service,
                        max_rounds=request.app.state.settings.agent_max_rounds,
                        on_tool_call=on_tool_call,
                    )
                else:
                    response = await answer_classic(
                        conn,
                        question=body.question,
                        embedder=embedder,
                        answerer=service,
                        limit=body.limit,
                        meeting_id=body.meeting_id,
                        use_index=body.use_index,
                    )
            await queue.put(("answer", response.model_dump(mode="json")))
        except AnswerUnavailable as exc:
            await queue.put(("error", {"detail": str(exc)}))
        except Exception:  # noqa: BLE001 - the headers are out; the client must still hear the end
            log.exception("answering failed mid-stream")
            await queue.put(("error", {"detail": "Answering failed on the server; the question was not answered."}))
        finally:
            await queue.put(None)

    async def events() -> AsyncIterator[str]:
        task = asyncio.create_task(work())
        try:
            while (item := await queue.get()) is not None:
                yield _event(*item)
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/traces", response_model=list[TraceSummary])
async def read_traces(conn: Conn, limit: Annotated[int, Query(ge=1, le=200)] = 50) -> list[TraceSummary]:
    """Every answered question, newest first, without the answer text."""
    return await list_traces(conn, limit=limit)


@app.get("/traces/{trace_id}", response_model=TraceDetail)
async def read_trace(trace_id: UUID, conn: Conn) -> TraceDetail:
    trace = await get_trace(conn, trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found.")
    return trace


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

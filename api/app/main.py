from fastapi import FastAPI, HTTPException, UploadFile

from app.models import MeetingResponse
from app.parsing import TranscriptParseError, parse_transcript

app = FastAPI(title="Meeting Intelligence API")


@app.post("/meetings", response_model=MeetingResponse)
async def create_meeting(file: UploadFile) -> MeetingResponse:
    """Ingest a transcript. For now that means parsing it into speaker turns;
    chunking, extraction and persistence will join this pipeline step by step."""
    try:
        raw = (await file.read()).decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="File must be UTF-8 encoded text.") from exc
    try:
        turns = parse_transcript(raw)
    except TranscriptParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return MeetingResponse(turns=turns)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

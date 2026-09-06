from pydantic import BaseModel


class Turn(BaseModel):
    """One speaker turn in a transcript, in the order it was spoken."""

    idx: int
    speaker: str
    start_seconds: int
    text: str


class MeetingResponse(BaseModel):
    turns: list[Turn]

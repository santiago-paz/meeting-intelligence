from pydantic import BaseModel


class Turn(BaseModel):
    """One speaker turn in a transcript, in the order it was spoken."""

    idx: int
    speaker: str
    start_seconds: int
    text: str


class MeetingResponse(BaseModel):
    turns: list[Turn]


class Chunk(BaseModel):
    """A window of consecutive whole turns, rendered as the text that gets embedded."""

    idx: int
    turn_start: int
    turn_end: int
    text: str
    token_estimate: int

"""Test mode: the model-backed services replayed from a recorded run.

Without an API key the app has nothing to show, so a real run is captured
once (api/record.py) into fixtures/test-mode.json: the context headers and
extracted rows of the sample meetings, and the answer Claude gave to every
golden question in both modes, with the tool calls it made. This module
plays that file back through the real pipeline. Citations still go through
the validator, traces are still written, retrieval still runs; only the
model's words are recorded.

Refs (M1, M2, ...) are numbered per run, so the recording names meetings by
title instead and every marker is translated on the way in and out.
"""

import re
import time
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.agentic import DEFAULT_MAX_ROUNDS, AgentRun, ToolError
from app.answering import NONE_MARKER, AnswerResult
from app.extraction import Extraction
from app.models import Chunk, SampleQuestion, ToolCall, Trace

REPLAY_MODEL = "test-mode"
RECORDING_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "test-mode.json"
_MARKER = re.compile(r"\[\[([A-Z]\d+)#(\d+)\]\]")
_PORTABLE_MARKER = re.compile(r"\[\[([^\[\]#]+)#(\d+)\]\]")
_EXCERPT_TAG = re.compile(r'<excerpt ref="([A-Z]\d+)" meeting="([^"]*)" turns="(\d+)-(\d+)"')
_MEETING_TAG = re.compile(r'<meeting ref="([A-Z]\d+)" title="([^"]*)"')
# Refs start at M1, so a marker sent to M0 is one the validator strips and counts.
DROPPED_REF = "M0"


def normalize_question(text: str) -> str:
    """The key a typed question is looked up by: case, spacing, accents and end punctuation aside."""
    plain = unicodedata.normalize("NFKD", text)
    plain = "".join(ch for ch in plain if not unicodedata.combining(ch))
    return " ".join(plain.lower().split()).rstrip(" ?.!¿¡")


def to_portable(text: str, ref_titles: dict[str, str]) -> str:
    """[[M1#7]] becomes [[<meeting title>#7]], so the marker survives renumbering."""

    def replace(match: re.Match) -> str:
        ref, turn = match.group(1), match.group(2)
        if ref not in ref_titles:
            raise ValueError(f"marker {match.group(0)} names {ref}, which this run has no title for")
        return f"[[{ref_titles[ref]}#{turn}]]"

    return _MARKER.sub(replace, text)


def from_portable(text: str, title_refs: dict[str, str]) -> str:
    """[[<meeting title>#7]] becomes [[M1#7]] in the refs of the current run.

    A title the run does not know goes to a ref that exists in no run, so the
    validator drops and counts it like any other unverifiable citation."""
    return _PORTABLE_MARKER.sub(
        lambda m: f"[[{title_refs.get(m.group(1), DROPPED_REF)}#{m.group(2)}]]", text
    )


def ref_titles_in_prompt(prompt: str) -> dict[str, str]:
    """Which ref stands for which meeting in a classic-mode prompt."""
    return {ref: title for ref, title, _, _ in _EXCERPT_TAG.findall(prompt)}


def ref_titles_in_index(system: list[dict]) -> dict[str, str]:
    """Which ref stands for which meeting in the agent's table of contents."""
    text = "\n".join(block.get("text", "") for block in system)
    return dict(_MEETING_TAG.findall(text))


def ranges_in_excerpts(text: str) -> list[tuple[str, int, int]]:
    """The (meeting title, first turn, last turn) of every excerpt in a tool result."""
    return [(title, int(start), int(end)) for _, title, start, end in _EXCERPT_TAG.findall(text)]


# ---- the recording ----


class StaleRecording(RuntimeError):
    """The recording no longer matches the code or the corpus."""


class RecordedMeeting(BaseModel):
    """What ingest asked the models for, per sample meeting: one header per chunk, and the extracted rows."""

    headers: list[str]
    extraction: Extraction


class RecordedCall(BaseModel):
    round: int
    name: str
    input: dict  # meeting_ref, when present, is a meeting title


class RecordedRange(BaseModel):
    """Turns the model was shown, by meeting title."""

    meeting: str
    turn_start: int
    turn_end: int


class RecordedAnswer(BaseModel):
    question: str
    type: str  # the golden set's question type, for grouping in the UI
    mode: Literal["classic", "agentic"]
    model: str  # what answered when it was recorded
    answer: str  # markers as [[<meeting title>#N]]
    refused: bool
    retrieved: list[RecordedRange] = []
    tool_calls: list[RecordedCall] = []
    rounds: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    latency_ms: int = 0


class Recording(BaseModel):
    recorded_at: str
    meetings: dict[str, RecordedMeeting]
    answers: list[RecordedAnswer]

    def find(self, question: str, mode: str) -> RecordedAnswer | None:
        key = normalize_question(question)
        return next((a for a in self.answers if a.mode == mode and normalize_question(a.question) == key), None)

    def questions(self) -> list[SampleQuestion]:
        """Each recorded question once, in recording order."""
        seen: dict[str, SampleQuestion] = {}
        for answer in self.answers:
            seen.setdefault(answer.question, SampleQuestion(question=answer.question, type=answer.type))
        return list(seen.values())


def answer_from_trace(trace: Trace, *, ref_titles: dict[str, str], question_type: str) -> RecordedAnswer:
    """A stored trace as the recording keeps it: every ref replaced by its meeting title."""

    def portable(inputs: dict) -> dict:
        ref = inputs.get("meeting_ref")
        if ref is None:
            return dict(inputs)
        if ref not in ref_titles:
            raise ValueError(f"tool call names {ref}, which this run has no title for")
        return {**inputs, "meeting_ref": ref_titles[ref]}

    return RecordedAnswer(
        question=trace.question, type=question_type, mode=trace.mode, model=trace.model,
        answer=to_portable(trace.answer, ref_titles), refused=trace.refused,
        retrieved=[RecordedRange(meeting=r.meeting_title, turn_start=r.turn_start, turn_end=r.turn_end) for r in trace.retrieved],
        tool_calls=[RecordedCall(round=c.round, name=c.name, input=portable(c.input)) for c in trace.tool_calls],
        rounds=trace.rounds, input_tokens=trace.input_tokens, output_tokens=trace.output_tokens,
        cache_read_tokens=trace.cache_read_tokens, cache_write_tokens=trace.cache_write_tokens,
        latency_ms=trace.latency_ms,
    )


# ---- ingest replay ----
class RecordedEnricher:
    def __init__(self, meeting: RecordedMeeting) -> None:
        self._headers = meeting.headers

    async def context_headers(self, transcript: str, chunks: list[Chunk]) -> list[str]:
        if len(chunks) != len(self._headers):
            raise StaleRecording(
                f"the recording has {len(self._headers)} context headers but the transcript now"
                f" cuts into {len(chunks)} chunks; re-run api/record.py"
            )
        return list(self._headers)


class RecordedExtractor:
    def __init__(self, meeting: RecordedMeeting) -> None:
        self._extraction = meeting.extraction

    async def extract(self, numbered_transcript: str, meeting_date) -> Extraction:
        return self._extraction


# ---- answer replay ----
def _replayed_text(recorded: RecordedAnswer, title_refs: dict[str, str]) -> str:
    text = from_portable(recorded.answer, title_refs)
    # The stored answer had its [[none]] stripped by the validator; put it back so the replay refuses too.
    return f"{text} {NONE_MARKER}".strip() if recorded.refused else text


def _inputs_in_refs(inputs: dict, title_refs: dict[str, str]) -> dict:
    title = inputs.get("meeting_ref")
    if title is None:
        return dict(inputs)
    return {**inputs, "meeting_ref": title_refs.get(title, DROPPED_REF)}


def _covered(wanted: RecordedRange, fetched: list[tuple[str, int, int]]) -> bool:
    return any(
        title == wanted.meeting and start <= wanted.turn_start and end >= wanted.turn_end
        for title, start, end in fetched
    )


class RecordedAnswerer:
    """Classic mode: retrieval is real; the words are recorded, spoken in this run's refs."""

    def __init__(self, recorded: RecordedAnswer) -> None:
        self._recorded = recorded

    async def answer(self, prompt: str) -> AnswerResult:
        title_refs = {title: ref for ref, title in ref_titles_in_prompt(prompt).items()}
        recorded = self._recorded
        return AnswerResult(
            text=_replayed_text(recorded, title_refs), model=REPLAY_MODEL, stop_reason="end_turn",
            input_tokens=recorded.input_tokens, output_tokens=recorded.output_tokens,
            cache_read_tokens=recorded.cache_read_tokens, cache_write_tokens=recorded.cache_write_tokens,
        )


class RecordedAgent:
    """Agentic mode: the recorded tool calls run again through the real executor,
    so every turn the answer cites was read in this run. If a search comes back
    with other excerpts than it did when recorded, the turns the model saw then
    are read explicitly, so the citations still check out."""

    def __init__(self, recorded: RecordedAnswer) -> None:
        self._recorded = recorded

    async def run(self, *, system, question, execute_tool, max_rounds=DEFAULT_MAX_ROUNDS, on_tool_call=None) -> AgentRun:
        title_refs = {title: ref for ref, title in ref_titles_in_index(system).items()}
        fetched: list[tuple[str, int, int]] = []
        calls: list[ToolCall] = []

        async def call(round_: int, name: str, inputs: dict) -> None:
            started = time.monotonic()
            try:
                text, summary = await execute_tool(name, inputs)
                fetched.extend(ranges_in_excerpts(text))
            except ToolError as exc:
                summary = f"error: {exc}"
            tool_call = ToolCall(
                round=round_, name=name, input=inputs, summary=summary,
                latency_ms=int((time.monotonic() - started) * 1000),
            )
            calls.append(tool_call)
            if on_tool_call is not None:
                await on_tool_call(tool_call)

        recorded = self._recorded
        for recorded_call in recorded.tool_calls:
            await call(recorded_call.round, recorded_call.name, _inputs_in_refs(recorded_call.input, title_refs))
        rounds = max((c.round for c in calls), default=0)
        missing = [wanted for wanted in recorded.retrieved if not _covered(wanted, fetched)]
        if missing:
            rounds += 1
            for wanted in missing:
                await call(rounds, "read_turns", {
                    "meeting_ref": title_refs.get(wanted.meeting, DROPPED_REF),
                    "start": wanted.turn_start, "end": wanted.turn_end,
                })
        return AgentRun(
            text=_replayed_text(recorded, title_refs), model=REPLAY_MODEL, stop_reason="end_turn",
            rounds=rounds, tool_calls=calls, input_tokens=recorded.input_tokens,
            output_tokens=recorded.output_tokens, cache_read_tokens=recorded.cache_read_tokens,
            cache_write_tokens=recorded.cache_write_tokens,
        )


@lru_cache(maxsize=1)
def load_recording(path: Path = RECORDING_PATH) -> "Recording":
    """The checked-in recording, read once."""
    if not path.exists():
        raise StaleRecording(f"{path} is missing; run api/record.py against a database with a real run in it")
    return Recording.model_validate_json(path.read_text(encoding="utf-8"))

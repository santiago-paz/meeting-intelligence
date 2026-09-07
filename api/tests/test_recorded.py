"""Test mode: the model-backed services replayed from a recorded run."""

from datetime import date
from uuid import uuid4

import pytest

from app.agentic import SYSTEM_RULES, ToolError, render_index
from app.answering import ChunkContext, build_prompt, validate_citations
from app.extraction import Extraction, ExtractedActionItem, ExtractedDecision
from app.models import Chunk, ChunkHit, Citation, MeetingOutline, RetrievedChunk, ToolCall, Trace, Turn
from app.recorded import (
    REPLAY_MODEL,
    RecordedAgent,
    RecordedAnswer,
    RecordedAnswerer,
    RecordedCall,
    RecordedEnricher,
    RecordedExtractor,
    RecordedMeeting,
    RecordedRange,
    Recording,
    StaleRecording,
    answer_from_trace,
    from_portable,
    normalize_question,
    ranges_in_excerpts,
    ref_titles_in_index,
    ref_titles_in_prompt,
    to_portable,
)

pytestmark = pytest.mark.anyio


def _context(ref: str, title: str, turn_start: int, turn_end: int) -> ChunkContext:
    meeting_id = uuid4()
    hit = ChunkHit(
        meeting_id=meeting_id, meeting_title=title, idx=0, turn_start=turn_start, turn_end=turn_end,
        text="", context_header=None, similarity=0.5,
    )
    turns = [Turn(idx=i, speaker="Ana", start_seconds=i * 10, text=f"turn {i}") for i in range(turn_start, turn_end + 1)]
    return ChunkContext(ref=ref, meeting_id=meeting_id, meeting_title=title, hit=hit, turns=turns)


# ---- questions ----
def test_normalize_question_ignores_case_spacing_punctuation_and_accents():
    assert normalize_question("  What did SOFÍA  say about the mobile app?? ") == "what did sofia say about the mobile app"


# ---- markers travel by meeting title, not by the ref of one run ----
def test_to_portable_replaces_refs_with_meeting_titles():
    text = "Ana leads it [[M1#7]] and said so again [[M2#3]][[M1#9]]."

    assert to_portable(text, {"M1": "q4-planning", "M2": "retro"}) == (
        "Ana leads it [[q4-planning#7]] and said so again [[retro#3]][[q4-planning#9]]."
    )


def test_to_portable_refuses_a_ref_it_cannot_name():
    with pytest.raises(ValueError, match="M3"):
        to_portable("Bogus [[M3#1]]", {"M1": "q4-planning"})


def test_from_portable_maps_titles_back_to_the_refs_in_use():
    text = "Ana leads it [[q4-planning#7]] and said so again [[retro#3]][[q4-planning#9]]."

    assert from_portable(text, {"q4-planning": "M2", "retro": "M1"}) == (
        "Ana leads it [[M2#7]] and said so again [[M1#3]][[M2#9]]."
    )


def test_from_portable_points_unknown_meetings_at_a_ref_the_validator_drops():
    text = from_portable("Marco agreed [[q4-planning#7]] and Diego too [[retro#3]].", {"retro": "M1"})

    check = validate_citations(text, [_context("M1", "retro", 0, 5)])
    assert check.answer == "Marco agreed and Diego too [[M1#3]]."
    assert check.dropped == 1
    assert [c.turn for c in check.citations] == [3]


# ---- reading the refs a run is using ----
def test_ref_titles_in_prompt_reads_the_excerpt_tags_classic_mode_writes():
    prompt = build_prompt("Who?", [_context("M1", "q4-planning", 0, 5), _context("M2", "retro", 3, 9), _context("M1", "q4-planning", 5, 9)])

    assert ref_titles_in_prompt(prompt) == {"M1": "q4-planning", "M2": "retro"}


def test_ref_titles_in_index_reads_the_meeting_tags_agentic_mode_writes():
    a, b = uuid4(), uuid4()
    outlines = [
        MeetingOutline(meeting_id=a, title="q4-planning", meeting_date=date(2026, 9, 1), turn_count=33, speakers=["Ana"], headers=[]),
        MeetingOutline(meeting_id=b, title="retro", meeting_date=None, turn_count=30, speakers=["Diego"], headers=[]),
    ]
    system = [
        {"type": "text", "text": SYSTEM_RULES},
        {"type": "text", "text": render_index(outlines, [], {a: "M1", b: "M2"}), "cache_control": {"type": "ephemeral"}},
    ]

    assert ref_titles_in_index(system) == {"M1": "q4-planning", "M2": "retro"}


def test_ranges_in_excerpts_reads_which_turns_a_tool_result_carried():
    text = (
        '<excerpt ref="M1" meeting="q4-planning" turns="0-15" similarity="0.71">\n#0 Ana: hi\n</excerpt>\n'
        '<excerpt ref="M2" meeting="retro" turns="3-9">\n#3 Diego: hey\n</excerpt>'
    )

    assert ranges_in_excerpts(text) == [("q4-planning", 0, 15), ("retro", 3, 9)]


def test_ranges_in_excerpts_is_empty_when_a_search_found_nothing():
    assert ranges_in_excerpts("No excerpts found.") == []


# ---- the recording ----

PLANNING, RETRO = uuid4(), uuid4()


def _trace(**overrides) -> Trace:
    base = dict(
        mode="agentic", question="Who leads the pricing page redesign?", model="claude-opus-5",
        answer="Ana [[M1#7]], still on the 8th [[M2#1]].", refused=False,
        citations=[
            Citation(ref="M1", meeting_id=PLANNING, meeting_title="q4-planning", turn=7, speaker="Marco", start_seconds=79, timestamp="00:01:19", text="Ana leads it"),
            Citation(ref="M2", meeting_id=RETRO, meeting_title="retro", turn=1, speaker="Ana", start_seconds=10, timestamp="00:00:10", text="Still me"),
        ],
        dropped_citations=0,
        retrieved=[
            RetrievedChunk(ref="M1", meeting_id=PLANNING, meeting_title="q4-planning", turn_start=0, turn_end=15, similarity=0.7),
            RetrievedChunk(ref="M2", meeting_id=RETRO, meeting_title="retro", turn_start=0, turn_end=9, similarity=None),
        ],
        input_tokens=1103, output_tokens=376, cache_read_tokens=900, cache_write_tokens=0, cost_usd=0.02,
        latency_ms=7389, index_rows=69,
        tool_calls=[
            ToolCall(round=1, name="search_transcripts", input={"query": "pricing owner", "meeting_ref": "M1"}, summary="1 excerpt(s)", latency_ms=43),
            ToolCall(round=1, name="search_transcripts", input={"query": "pricing", "meeting_ref": None}, summary="2 excerpt(s)", latency_ms=20),
            ToolCall(round=2, name="read_turns", input={"meeting_ref": "M2", "start": 0, "end": 9}, summary="M2 turns 0-9", latency_ms=5),
        ],
        rounds=2,
    )
    return Trace(**{**base, **overrides})


def _recorded(**overrides) -> RecordedAnswer:
    base = dict(
        question="Who leads the pricing page redesign?", type="lookup", mode="agentic", model="claude-opus-5",
        answer="Ana [[q4-planning#7]], still on the 8th [[retro#1]].", refused=False,
        retrieved=[RecordedRange(meeting="q4-planning", turn_start=0, turn_end=15), RecordedRange(meeting="retro", turn_start=0, turn_end=9)],
        tool_calls=[
            RecordedCall(round=1, name="search_transcripts", input={"query": "pricing owner", "meeting_ref": "q4-planning"}),
            RecordedCall(round=2, name="read_turns", input={"meeting_ref": "retro", "start": 0, "end": 9}),
        ],
        rounds=2, input_tokens=1103, output_tokens=376, cache_read_tokens=900, cache_write_tokens=0, latency_ms=7389,
    )
    return RecordedAnswer(**{**base, **overrides})


def test_answer_from_trace_names_meetings_by_title_everywhere_a_ref_appears():
    recorded = answer_from_trace(_trace(), ref_titles={"M1": "q4-planning", "M2": "retro"}, question_type="lookup")

    assert recorded.answer == "Ana [[q4-planning#7]], still on the 8th [[retro#1]]."
    assert [c.input for c in recorded.tool_calls] == [
        {"query": "pricing owner", "meeting_ref": "q4-planning"},
        {"query": "pricing", "meeting_ref": None},
        {"meeting_ref": "retro", "start": 0, "end": 9},
    ]
    assert [(r.meeting, r.turn_start, r.turn_end) for r in recorded.retrieved] == [("q4-planning", 0, 15), ("retro", 0, 9)]
    assert (recorded.mode, recorded.type, recorded.model, recorded.rounds) == ("agentic", "lookup", "claude-opus-5", 2)
    assert (recorded.input_tokens, recorded.output_tokens, recorded.cache_read_tokens) == (1103, 376, 900)
    assert recorded.refused is False


def test_answer_from_trace_keeps_the_refusal_flag():
    recorded = answer_from_trace(_trace(answer="Not covered.", refused=True, citations=[]), ref_titles={"M1": "q4-planning", "M2": "retro"}, question_type="unanswerable")

    assert recorded.refused is True


def test_recording_finds_an_answer_by_normalized_question_and_mode():
    recording = Recording(recorded_at="2026-09-07", meetings={}, answers=[_recorded(), _recorded(mode="classic", tool_calls=[], rounds=0)])

    assert recording.find("who leads the PRICING page redesign", "classic").mode == "classic"
    assert recording.find("Who leads the pricing page redesign?", "agentic").mode == "agentic"
    assert recording.find("Who leads what?", "agentic") is None


def test_recording_lists_each_question_once_with_its_type_in_order():
    recording = Recording(
        recorded_at="2026-09-07", meetings={},
        answers=[_recorded(), _recorded(mode="classic"), _recorded(question="What is the SOC 2 timeline?", type="temporal")],
    )

    assert [(q.question, q.type) for q in recording.questions()] == [
        ("Who leads the pricing page redesign?", "lookup"),
        ("What is the SOC 2 timeline?", "temporal"),
    ]


# ---- ingest replay ----
def _chunks(n: int) -> list[Chunk]:
    return [Chunk(idx=i, turn_start=i, turn_end=i, text=f"#{i}", token_estimate=1) for i in range(n)]


async def test_recorded_enricher_returns_the_recorded_headers_for_the_chunks():
    enricher = RecordedEnricher(RecordedMeeting(headers=["first", "second"], extraction=Extraction(decisions=[], action_items=[])))

    assert await enricher.context_headers("raw", _chunks(2)) == ["first", "second"]


async def test_recorded_enricher_refuses_when_the_chunking_no_longer_matches_the_recording():
    enricher = RecordedEnricher(RecordedMeeting(headers=["first", "second"], extraction=Extraction(decisions=[], action_items=[])))

    with pytest.raises(StaleRecording, match="record.py"):
        await enricher.context_headers("raw", _chunks(3))


async def test_recorded_extractor_returns_the_recorded_rows():
    extraction = Extraction(
        decisions=[ExtractedDecision(statement="No mobile app in Q4.", decided_by="Marco", turn=25, confidence=0.9)],
        action_items=[ExtractedActionItem(task="Write the deploy process.", owner="Diego", turn=28)],
    )
    extractor = RecordedExtractor(RecordedMeeting(headers=[], extraction=extraction))

    assert await extractor.extract("#0 Marco: hi", date(2026, 9, 1)) == extraction


# ---- answer replay ----
async def test_recorded_answerer_speaks_in_the_refs_of_the_prompt_it_is_given():
    answerer = RecordedAnswerer(_recorded(mode="classic", tool_calls=[], rounds=0))

    result = await answerer.answer(build_prompt("Who?", [_context("M1", "retro", 0, 9), _context("M2", "q4-planning", 0, 15)]))

    assert result.text == "Ana [[M2#7]], still on the 8th [[M1#1]]."
    assert (result.model, result.stop_reason) == (REPLAY_MODEL, "end_turn")
    assert (result.input_tokens, result.output_tokens, result.cache_read_tokens, result.cache_write_tokens) == (1103, 376, 900, 0)


async def test_recorded_answerer_puts_the_none_marker_back_on_a_refusal():
    answerer = RecordedAnswerer(_recorded(mode="classic", answer="The meetings do not say.", refused=True, tool_calls=[], rounds=0))

    result = await answerer.answer(build_prompt("Revenue?", [_context("M1", "retro", 0, 9)]))

    assert validate_citations(result.text, []).refused is True
    assert validate_citations(result.text, []).answer == "The meetings do not say."


def _system(title_refs: dict[str, str]) -> list[dict]:
    outlines, refs = [], {}
    for title, ref in title_refs.items():
        meeting_id = uuid4()
        outlines.append(MeetingOutline(meeting_id=meeting_id, title=title, meeting_date=None, turn_count=40, speakers=[], headers=[]))
        refs[meeting_id] = ref
    return [{"type": "text", "text": SYSTEM_RULES}, {"type": "text", "text": render_index(outlines, [], refs)}]


def _excerpt(ref: str, title: str, start: int, end: int) -> str:
    return f'<excerpt ref="{ref}" meeting="{title}" turns="{start}-{end}">\n#{start} Ana: words\n</excerpt>'


class _Executor:
    """Answers search calls with the excerpts it is told to; reads return exactly the range asked."""

    def __init__(self, title_refs: dict[str, str], search_results: list[tuple[str, int, int]]) -> None:
        self.title_refs = title_refs
        self.search_results = search_results
        self.calls: list[tuple[str, dict]] = []

    async def __call__(self, name: str, inputs: dict) -> tuple[str, str]:
        self.calls.append((name, dict(inputs)))
        if name == "search_transcripts":
            text = "\n".join(_excerpt(self.title_refs[t], t, s, e) for t, s, e in self.search_results)
            return text or "No excerpts found.", f"{len(self.search_results)} excerpt(s)"
        if name == "read_turns":
            title = next((t for t, r in self.title_refs.items() if r == inputs["meeting_ref"]), None)
            if title is None:
                raise ToolError(f"unknown meeting ref {inputs['meeting_ref']}")
            return _excerpt(inputs["meeting_ref"], title, inputs["start"], inputs["end"]), f"{inputs['meeting_ref']} turns {inputs['start']}-{inputs['end']}"
        raise ToolError(f"unknown tool {name}")


async def test_recorded_agent_replays_each_recorded_call_in_the_refs_of_this_run_and_reports_it():
    title_refs = {"retro": "M1", "q4-planning": "M2"}  # numbered differently from the recording
    executor = _Executor(title_refs, search_results=[("q4-planning", 0, 15)])
    seen: list[ToolCall] = []

    async def on_tool_call(call: ToolCall) -> None:
        seen.append(call)

    run = await RecordedAgent(_recorded()).run(system=_system(title_refs), question="ignored", execute_tool=executor, on_tool_call=on_tool_call)

    assert executor.calls == [
        ("search_transcripts", {"query": "pricing owner", "meeting_ref": "M2"}),
        ("read_turns", {"meeting_ref": "M1", "start": 0, "end": 9}),
    ]
    assert [(c.round, c.name, c.summary) for c in run.tool_calls] == [(1, "search_transcripts", "1 excerpt(s)"), (2, "read_turns", "M1 turns 0-9")]
    assert [c.name for c in seen] == ["search_transcripts", "read_turns"]
    assert run.text == "Ana [[M2#7]], still on the 8th [[M1#1]]."
    assert (run.model, run.stop_reason, run.rounds) == (REPLAY_MODEL, "end_turn", 2)
    assert (run.input_tokens, run.output_tokens, run.cache_read_tokens, run.cache_write_tokens) == (1103, 376, 900, 0)


async def test_recorded_agent_reads_any_recorded_range_the_replay_did_not_fetch():
    title_refs = {"q4-planning": "M1", "retro": "M2"}
    # The search comes back with a different excerpt than it did when recorded.
    executor = _Executor(title_refs, search_results=[("q4-planning", 15, 32)])

    run = await RecordedAgent(_recorded()).run(system=_system(title_refs), question="ignored", execute_tool=executor)

    assert executor.calls[-1] == ("read_turns", {"meeting_ref": "M1", "start": 0, "end": 15})
    assert [(c.round, c.name) for c in run.tool_calls] == [(1, "search_transcripts"), (2, "read_turns"), (3, "read_turns")]
    assert run.rounds == 3


async def test_recorded_agent_reports_a_tool_error_the_way_the_real_agent_does():
    title_refs = {"q4-planning": "M1"}  # the retro is not loaded
    executor = _Executor(title_refs, search_results=[("q4-planning", 0, 15)])

    run = await RecordedAgent(_recorded()).run(system=_system(title_refs), question="ignored", execute_tool=executor)

    read = next(c for c in run.tool_calls if c.name == "read_turns" and c.input.get("start") == 0 and c.input.get("end") == 9)
    assert read.summary.startswith("error:")
    assert read.input["meeting_ref"] == "M0"

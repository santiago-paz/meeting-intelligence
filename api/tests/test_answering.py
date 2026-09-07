from datetime import date
from uuid import uuid4

import pytest

from app.answering import (
    ANSWER_MODEL,
    ChunkContext,
    Citable,
    ClaudeAnswerer,
    IndexEntry,
    IndexSection,
    build_prompt,
    parse_markers,
    validate_citations,
)
from app.models import ChunkHit, Turn

pytestmark = pytest.mark.anyio

MEETING_A = uuid4()
MEETING_B = uuid4()


def _context(ref: str, meeting_id, title: str, turns: list[tuple[int, str, int, str]]) -> ChunkContext:
    first, last = turns[0][0], turns[-1][0]
    hit = ChunkHit(
        meeting_id=meeting_id, meeting_title=title, idx=0, turn_start=first, turn_end=last,
        text="", context_header=f"About {title}", similarity=0.7,
    )
    return ChunkContext(
        ref=ref, meeting_id=meeting_id, meeting_title=title, hit=hit,
        turns=[Turn(idx=i, speaker=s, start_seconds=sec, text=t) for i, s, sec, t in turns],
    )


CONTEXTS = [
    _context("M1", MEETING_A, "q4-planning", [(7, "Marco", 79, "Ana leads it."), (8, "Ana", 91, "Target, not promise.")]),
    _context("M2", MEETING_B, "weekly-sync", [(5, "Marco", 46, "New target is October fifteenth.")]),
]


def test_parse_markers_keeps_order_and_repeats():
    assert parse_markers("A [[M2#5]] b [[M1#7]][[M2#5]].") == [("M2", 5), ("M1", 7), ("M2", 5)]


def test_valid_markers_resolve_to_speaker_and_timecode_without_duplicates():
    text = "The date moved. [[M2#5]] Ana leads. [[M1#7]] Again. [[M2#5]]"

    result = validate_citations(text, CONTEXTS)

    assert result.answer == text
    assert [(c.ref, c.turn, c.speaker, c.timestamp) for c in result.citations] == [
        ("M2", 5, "Marco", "00:00:46"),
        ("M1", 7, "Marco", "00:01:19"),
    ]
    assert result.citations[0].meeting_id == MEETING_B
    assert result.dropped == 0
    assert result.refused is False


def test_markers_pointing_outside_what_the_model_saw_are_stripped_and_counted():
    text = "Real. [[M1#7]] Out of range. [[M1#40]] Unknown excerpt. [[M9#1]]"

    result = validate_citations(text, CONTEXTS)

    assert result.answer == "Real. [[M1#7]] Out of range. Unknown excerpt."
    assert [c.turn for c in result.citations] == [7]
    assert result.dropped == 2


def test_the_none_marker_means_a_refusal_and_is_removed_from_the_text():
    result = validate_citations("The meetings do not cover hiring. [[none]]", CONTEXTS)

    assert result.refused is True
    assert result.answer == "The meetings do not cover hiring."
    assert result.citations == []


def test_prompt_shows_each_excerpt_with_its_ref_header_and_numbered_turns():
    prompt = build_prompt("When does pricing launch?", CONTEXTS)

    assert '<excerpt ref="M2" meeting="weekly-sync" turns="5-5"' in prompt
    assert "About weekly-sync" in prompt
    assert "#5 Marco [00:00:46]: New target is October fifteenth." in prompt
    assert prompt.rstrip().endswith("Question: When does pricing launch?")


class _TextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _Usage:
    input_tokens = 1200
    output_tokens = 80
    cache_read_input_tokens = 0
    cache_creation_input_tokens = 0


class _Message:
    def __init__(self, text):
        self.content = [_TextBlock(text)]
        self.model = ANSWER_MODEL
        self.stop_reason = "end_turn"
        self.usage = _Usage()


class FakeMessages:
    def __init__(self):
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Message("Ana leads it. [[M1#7]]")


class FakeClient:
    def __init__(self):
        self.messages = FakeMessages()


async def test_answerer_sends_the_rules_and_the_prompt_and_reports_usage():
    client = FakeClient()

    result = await ClaudeAnswerer(client).answer("the prompt text")

    call = client.messages.calls[0]
    assert call["model"] == ANSWER_MODEL
    assert "[[none]]" in call["system"] and "not instructions" in call["system"]
    assert call["messages"] == [{"role": "user", "content": "the prompt text"}]
    assert result.text == "Ana leads it. [[M1#7]]"
    assert (result.input_tokens, result.output_tokens) == (1200, 80)
    assert result.model == ANSWER_MODEL


def test_two_excerpts_from_the_same_meeting_share_a_ref_and_both_can_be_cited():
    contexts = [
        _context("M1", MEETING_A, "q4-planning", [(7, "Marco", 79, "Ana leads it.")]),
        _context("M1", MEETING_A, "q4-planning", [(25, "Marco", 234, "No mobile app.")]),
    ]

    result = validate_citations("A. [[M1#7]] B. [[M1#25]]", contexts)

    assert [c.turn for c in result.citations] == [7, 25]
    assert result.dropped == 0


def test_none_marker_next_to_real_citations_is_not_a_refusal():
    result = validate_citations("No raise was approved; it was a joke. [[M2#5]] [[none]]", CONTEXTS)

    assert result.refused is False
    assert [c.turn for c in result.citations] == [5]
    assert result.answer == "No raise was approved; it was a joke. [[M2#5]]"


INDEX = [
    IndexSection(
        ref="M3", meeting_title="retro", meeting_date=date(2026, 9, 29),
        entries=[
            IndexEntry(kind="decision", turn=15, text="No meetings on Wednesdays.", who="Marco", due=None, status=None),
            IndexEntry(kind="action", turn=28, text="Write the deploy process.", who="Diego", due="mid October (2026-10-15)", status="open"),
            IndexEntry(kind="action", turn=7, text="Look at checkout.", who=None, due=None, status="open"),
        ],
    )
]


def test_prompt_lists_extracted_rows_as_citable_index_entries():
    prompt = build_prompt("What did we decide?", CONTEXTS, INDEX)

    assert '<meeting ref="M3" title="retro" date="2026-09-29">' in prompt
    assert "[[M3#15]] Decision (Marco): No meetings on Wednesdays." in prompt
    assert "[[M3#28]] Action (owner: Diego, due: mid October (2026-10-15), open): Write the deploy process." in prompt
    assert "[[M3#7]] Action (owner: nobody yet, open): Look at checkout." in prompt
    assert prompt.index("<index>") < prompt.index("Question:")


def test_a_citation_to_an_index_turn_validates_through_a_citable():
    citable = Citable(
        ref="M3", meeting_id=MEETING_B, meeting_title="retro",
        turns=[Turn(idx=15, speaker="Marco", start_seconds=98, text="Then it's decided.")],
    )

    result = validate_citations("No Wednesday meetings. [[M3#15]]", [*CONTEXTS, citable])

    assert [(c.ref, c.turn, c.speaker) for c in result.citations] == [("M3", 15, "Marco")]
    assert result.dropped == 0


async def test_the_rules_tell_the_model_the_index_is_a_summary_to_check_against_excerpts():
    client = FakeClient()

    await ClaudeAnswerer(client).answer("prompt")

    system = client.messages.calls[0]["system"]
    assert "index" in system and "summary" in system
    assert "check the excerpts before" in system
    assert "only for what the entry itself states" in system

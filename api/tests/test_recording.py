"""The checked-in recording must match the corpus and the code it will be replayed through.

fixtures/test-mode.json is written by api/record.py from a real run. If a
transcript is edited, the chunker changes, or a golden question is added, this
fails instead of letting test mode replay answers that no longer fit.
"""

import json
from pathlib import Path

import pytest

from app.chunking import build_chunks
from app.parsing import parse_transcript
from app.recorded import RECORDING_PATH, _PORTABLE_MARKER, load_recording

ROOT = Path(__file__).resolve().parents[2] / "fixtures"
GOLDEN = json.loads((ROOT / "golden.json").read_text(encoding="utf-8"))["questions"]
TRANSCRIPTS = {
    path.stem: parse_transcript(path.read_text(encoding="utf-8-sig"))
    for path in (ROOT / "transcripts").glob("*.txt")
}
RECORDING = load_recording()


def test_the_recording_lives_next_to_the_transcripts_it_replays():
    assert RECORDING_PATH == ROOT / "test-mode.json"
    assert RECORDING.recorded_at


def test_every_sample_meeting_is_recorded_with_one_header_per_chunk():
    assert set(RECORDING.meetings) == set(TRANSCRIPTS)
    for title, meeting in RECORDING.meetings.items():
        chunks = build_chunks(TRANSCRIPTS[title])
        assert len(meeting.headers) == len(chunks), f"{title}: {len(meeting.headers)} headers for {len(chunks)} chunks"
        assert all(h.strip() for h in meeting.headers)


@pytest.mark.parametrize("title", sorted(TRANSCRIPTS), ids=sorted(TRANSCRIPTS))
def test_recorded_rows_point_at_real_turns(title: str):
    meeting = RECORDING.meetings[title]
    turn_count = len(TRANSCRIPTS[title])
    assert meeting.extraction.decisions or meeting.extraction.action_items
    for row in [*meeting.extraction.decisions, *meeting.extraction.action_items]:
        assert 0 <= row.turn < turn_count, f"{title} has no turn {row.turn}"


def test_every_golden_question_is_answered_in_both_modes():
    recorded = {(a.question, a.mode) for a in RECORDING.answers}
    expected = {(q["question"], mode) for q in GOLDEN for mode in ("classic", "agentic")}
    assert recorded == expected
    assert [q.question for q in RECORDING.questions()] == [q["question"] for q in GOLDEN]
    assert {q.type for q in RECORDING.questions()} == {q["type"] for q in GOLDEN}


@pytest.mark.parametrize("answer", RECORDING.answers, ids=[f"{a.mode}-{a.question[:30]}" for a in RECORDING.answers])
def test_recorded_answers_cite_turns_that_exist_and_read_ranges_that_exist(answer):
    for title, turn in _PORTABLE_MARKER.findall(answer.answer):
        assert title in TRANSCRIPTS, f"marker names unknown meeting {title!r}"
        assert 0 <= int(turn) < len(TRANSCRIPTS[title]), f"{title} has no turn {turn}"
    assert "[[M" not in answer.answer, "markers must travel by title, not by ref"
    for r in answer.retrieved:
        assert r.meeting in TRANSCRIPTS
        assert 0 <= r.turn_start <= r.turn_end < len(TRANSCRIPTS[r.meeting])
    for call in answer.tool_calls:
        ref = call.input.get("meeting_ref")
        assert ref is None or ref in TRANSCRIPTS, f"tool call names unknown meeting {ref!r}"
    if answer.mode == "classic":
        assert not answer.tool_calls
    else:
        assert answer.tool_calls and answer.rounds >= 1
    assert answer.model.startswith("claude-")
    assert answer.input_tokens > 0 and answer.output_tokens > 0


def test_a_refusal_is_recorded_without_markers_and_an_answer_with_them():
    for answer in RECORDING.answers:
        cited = bool(_PORTABLE_MARKER.search(answer.answer))
        assert cited != answer.refused, f"{answer.mode} {answer.question!r}: refused={answer.refused} but cited={cited}"

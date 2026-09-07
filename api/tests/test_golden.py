"""The golden question set must point at real turns that say what it claims.

Every answerable question lists the turns that support its answer, each with a
short verbatim quote. If a transcript is edited and turns shift, this fails
instead of letting the eval silently grade against the wrong lines.
"""

import json
from collections import Counter
from pathlib import Path

import pytest

from app.parsing import parse_transcript

ROOT = Path(__file__).resolve().parents[2] / "fixtures"
GOLDEN = json.loads((ROOT / "golden.json").read_text(encoding="utf-8"))
TRANSCRIPTS = {
    path.stem: parse_transcript(path.read_text(encoding="utf-8"))
    for path in (ROOT / "transcripts").glob("*.txt")
}
QUESTIONS = GOLDEN["questions"]


def test_has_about_twenty_questions_covering_every_type():
    types = Counter(q["type"] for q in QUESTIONS)
    assert len(QUESTIONS) >= 20
    assert {"lookup", "aggregation", "temporal", "speaker", "unanswerable"} <= set(types)
    assert types["unanswerable"] >= 3


def test_ids_are_unique():
    ids = [q["id"] for q in QUESTIONS]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("q", QUESTIONS, ids=[q["id"] for q in QUESTIONS])
def test_expected_turns_exist_and_carry_their_quote(q):
    if q["expect_refusal"]:
        assert q["expected_turns"] == [], "a refusal question has no supporting turns"
        return
    assert q["expected_turns"], "an answerable question needs supporting turns"
    for ref in q["expected_turns"]:
        turns = TRANSCRIPTS[ref["meeting"]]
        assert 0 <= ref["turn"] < len(turns), f"{ref['meeting']} has no turn {ref['turn']}"
        text = turns[ref["turn"]].text
        assert ref["quote"] in text, f"{ref['meeting']}#{ref['turn']} does not say {ref['quote']!r}: {text[:90]}"


@pytest.mark.parametrize("q", QUESTIONS, ids=[q["id"] for q in QUESTIONS])
def test_every_question_has_atomic_key_facts(q):
    """The judge scores facts one by one, so each question must name them."""
    minimum = 1 if q["expect_refusal"] else 2
    assert len(q["key_facts"]) >= minimum
    assert all(isinstance(fact, str) and fact.strip() for fact in q["key_facts"])

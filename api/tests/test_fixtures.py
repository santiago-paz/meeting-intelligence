"""The sample corpus must stay parseable: every fixture is a real conversation."""

from pathlib import Path

import pytest

from app.parsing import parse_transcript

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "transcripts"
FIXTURES = sorted(FIXTURES_DIR.glob("*.txt"))


def test_the_corpus_has_at_least_five_meetings():
    assert len(FIXTURES) >= 5


@pytest.mark.parametrize("path", FIXTURES, ids=[p.stem for p in FIXTURES])
def test_fixture_parses_into_a_real_conversation(path: Path):
    turns = parse_transcript(path.read_text(encoding="utf-8"))

    assert len(turns) >= 25
    assert len({t.speaker for t in turns}) >= 3
    seconds = [t.start_seconds for t in turns]
    assert seconds == sorted(seconds), "timestamps must not go backwards"


def test_wrapped_lines_join_the_turn_above_them():
    text = (FIXTURES_DIR / "2026-09-08-weekly-sync.txt").read_text(encoding="utf-8")
    roadmap = next(t for t in parse_transcript(text) if "one thing at a time" in t.text)
    assert roadmap.speaker == "Marco"
    assert "tell me, because it means I was wrong" in roadmap.text

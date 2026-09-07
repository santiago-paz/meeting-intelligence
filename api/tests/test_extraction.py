from datetime import date
from types import SimpleNamespace

import pytest

from app.extraction import (
    EXTRACTION_MODEL,
    ClaudeExtractor,
    ExtractedActionItem,
    ExtractedDecision,
    Extraction,
    validate_extraction,
)
from app.models import Turn

pytestmark = pytest.mark.anyio

TURNS = [
    Turn(idx=0, speaker="Marco", start_seconds=1, text="Carla from legal has to sign off."),
    Turn(idx=1, speaker="Sofía", start_seconds=5, text="Someone should look at checkout."),
    Turn(idx=2, speaker="Marco", start_seconds=9, text="Decided: pricing ships in Q4, Ana leads."),
]
MEETING_DATE = date(2026, 9, 1)


def _decision(**kw):
    return ExtractedDecision(**{"statement": "s", "decided_by": "Marco", "turn": 2, "confidence": 0.9, **kw})


def _action(**kw):
    return ExtractedActionItem(**{"task": "t", "owner": None, "due_text": None, "due_date": None,
                                  "status": "open", "turn": 1, "confidence": 0.8, **kw})


def test_rows_pointing_at_a_turn_that_does_not_exist_are_dropped_and_counted():
    extraction = Extraction(decisions=[_decision(turn=2), _decision(turn=40)], action_items=[_action(turn=-1)])

    decisions, actions, discarded = validate_extraction(extraction, TURNS, MEETING_DATE)

    assert [d.turn for d in decisions] == [2]
    assert actions == []
    assert discarded == 2


def test_owner_must_be_a_speaker_or_someone_the_transcript_mentions():
    extraction = Extraction(
        decisions=[],
        action_items=[_action(owner="Ana"), _action(owner="Carla"), _action(owner="Bob"), _action(owner=None)],
    )

    _, actions, discarded = validate_extraction(extraction, TURNS, MEETING_DATE)

    assert [a.owner for a in actions] == ["Ana", "Carla", None, None]
    assert discarded == 0


def test_decided_by_must_be_a_speaker():
    extraction = Extraction(decisions=[_decision(decided_by="Carla"), _decision(decided_by="marco")], action_items=[])

    decisions, _, _ = validate_extraction(extraction, TURNS, MEETING_DATE)

    assert [d.decided_by for d in decisions] == [None, "Marco"]


def test_due_dates_parse_and_cannot_precede_the_meeting():
    extraction = Extraction(
        decisions=[],
        action_items=[
            _action(due_text="by Friday", due_date="2026-09-05"),
            _action(due_text="last week", due_date="2026-08-20"),
            _action(due_text="soon", due_date="not a date"),
        ],
    )

    _, actions, _ = validate_extraction(extraction, TURNS, MEETING_DATE)

    assert [a.due_date for a in actions] == [date(2026, 9, 5), None, None]
    assert [a.due_text for a in actions] == ["by Friday", "last week", "soon"]


def test_status_and_confidence_are_normalised():
    extraction = Extraction(
        decisions=[_decision(confidence=1.7)],
        action_items=[_action(status="DONE"), _action(status="whatever", confidence=-2)],
    )

    decisions, actions, _ = validate_extraction(extraction, TURNS, MEETING_DATE)

    assert decisions[0].confidence == 1.0
    assert [a.status for a in actions] == ["done", "open"]
    assert actions[1].confidence == 0.0


class FakeParseMessages:
    def __init__(self, output):
        self.output = output
        self.calls = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(parsed_output=self.output)


async def test_extractor_sends_the_numbered_transcript_and_the_meeting_date():
    output = Extraction(decisions=[_decision()], action_items=[])
    client = SimpleNamespace(messages=FakeParseMessages(output))

    result = await ClaudeExtractor(client).extract("#0 Marco [00:00:01]: Hi.", MEETING_DATE)

    call = client.messages.calls[0]
    assert call["model"] == EXTRACTION_MODEL
    assert call["output_format"] is Extraction
    assert "#0 Marco [00:00:01]: Hi." in call["messages"][0]["content"]
    assert "2026-09-01" in call["messages"][0]["content"]
    assert "not instructions" in call["system"]
    assert result is output

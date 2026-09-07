from uuid import uuid4

import pytest

from app.models import Chunk, Turn
from app.repository import get_meeting, insert_meeting, list_meetings

pytestmark = pytest.mark.anyio

TURNS = [
    Turn(idx=0, speaker="Marco", start_seconds=724, text="Que hacemos con pricing?"),
    Turn(idx=1, speaker="Ana", start_seconds=731, text="Lo tengo para fin de mes."),
]
CHUNKS = [
    Chunk(
        idx=0,
        turn_start=0,
        turn_end=1,
        text="Marco [00:12:04]: Que hacemos con pricing?\nAna [00:12:11]: Lo tengo para fin de mes.",
        token_estimate=21,
    )
]


async def test_insert_meeting_and_read_it_back(migrated_conn):
    meeting_id = await insert_meeting(
        migrated_conn, title="Q4 Planning", source_filename="q4.txt", turns=TURNS, chunks=CHUNKS
    )

    meeting = await get_meeting(migrated_conn, meeting_id)

    assert meeting.id == meeting_id
    assert meeting.title == "Q4 Planning"
    assert meeting.turns == TURNS
    cur = await migrated_conn.execute(
        "SELECT count(*) FROM chunks WHERE meeting_id = %s", (meeting_id,)
    )
    assert (await cur.fetchone())[0] == 1


async def test_list_meetings_newest_first_with_turn_counts(migrated_conn):
    first = await insert_meeting(
        migrated_conn, title="First", source_filename="a.txt", turns=TURNS, chunks=CHUNKS
    )
    second = await insert_meeting(
        migrated_conn, title="Second", source_filename="b.txt", turns=TURNS[:1], chunks=[]
    )

    meetings = await list_meetings(migrated_conn)

    assert [(m.title, m.turn_count) for m in meetings] == [("Second", 1), ("First", 2)]
    assert [m.id for m in meetings] == [second, first]


async def test_get_missing_meeting_returns_none(migrated_conn):
    assert await get_meeting(migrated_conn, uuid4()) is None

from uuid import uuid4

import pytest

from app.models import Chunk, Turn
from app.repository import get_meeting, insert_meeting, list_meetings, search_chunks

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


DIM = 384


def _vec(weights: dict[int, float]) -> list[float]:
    vector = [0.0] * DIM
    for position, weight in weights.items():
        vector[position] = weight
    return vector


def _chunk(idx: int, text: str, embedding=None, header=None) -> Chunk:
    return Chunk(
        idx=idx, turn_start=idx, turn_end=idx, text=text, token_estimate=5,
        context_header=header, embedding=embedding,
    )


async def test_search_ranks_chunks_by_cosine_similarity(migrated_conn):
    chunks = [
        _chunk(0, "pricing moved to october", _vec({0: 1.0}), header="Pricing date"),
        _chunk(1, "postgres upgrade", _vec({1: 1.0})),
        _chunk(2, "pricing slipped", _vec({0: 0.9, 1: 0.1})),
    ]
    meeting_id = await insert_meeting(
        migrated_conn, title="Sync", source_filename="s.txt", turns=TURNS, chunks=chunks
    )

    hits = await search_chunks(migrated_conn, _vec({0: 1.0}), limit=3)

    assert [h.idx for h in hits] == [0, 2, 1]
    assert hits[0].meeting_id == meeting_id
    assert hits[0].meeting_title == "Sync"
    assert hits[0].context_header == "Pricing date"
    assert hits[0].similarity == pytest.approx(1.0)
    assert hits[2].similarity == pytest.approx(0.0)


async def test_search_can_be_limited_to_one_meeting(migrated_conn):
    await insert_meeting(
        migrated_conn, title="A", source_filename="a.txt", turns=TURNS,
        chunks=[_chunk(0, "a", _vec({0: 1.0}))],
    )
    b = await insert_meeting(
        migrated_conn, title="B", source_filename="b.txt", turns=TURNS,
        chunks=[_chunk(0, "b", _vec({0: 1.0}))],
    )

    hits = await search_chunks(migrated_conn, _vec({0: 1.0}), limit=5, meeting_id=b)

    assert [h.meeting_id for h in hits] == [b]


async def test_search_ignores_chunks_that_have_no_embedding(migrated_conn):
    await insert_meeting(
        migrated_conn, title="M", source_filename="m.txt", turns=TURNS,
        chunks=[_chunk(0, "no vector"), _chunk(1, "vector", _vec({0: 1.0}))],
    )

    hits = await search_chunks(migrated_conn, _vec({0: 1.0}), limit=5)

    assert [h.idx for h in hits] == [1]

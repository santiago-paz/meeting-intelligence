from uuid import uuid4

from app.ask import assign_refs
from app.models import ChunkHit


def _hit(meeting_id, idx=0):
    return ChunkHit(
        meeting_id=meeting_id, meeting_title="t", idx=idx, turn_start=0, turn_end=1,
        text="", context_header=None, similarity=0.5,
    )


def test_assign_refs_gives_one_ref_per_meeting_in_order_of_first_appearance():
    a, b = uuid4(), uuid4()

    assert assign_refs([_hit(a), _hit(b), _hit(a, idx=1)]) == {a: "M1", b: "M2"}

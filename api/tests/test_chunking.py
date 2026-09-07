from app.chunking import build_chunks, estimate_tokens
from app.models import Turn


def _turn(idx: int, text: str, speaker: str = "A") -> Turn:
    return Turn(idx=idx, speaker=speaker, start_seconds=idx + 1, text=text)


def test_puts_everything_in_one_chunk_when_it_fits():
    turns = [
        Turn(idx=0, speaker="Marco", start_seconds=724, text="Que hacemos con pricing?"),
        Turn(idx=1, speaker="Ana", start_seconds=731, text="Lo tengo para fin de mes."),
    ]

    chunks = build_chunks(turns, max_tokens=500)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.idx == 0
    assert (chunk.turn_start, chunk.turn_end) == (0, 1)
    assert chunk.text == (
        "Marco [00:12:04]: Que hacemos con pricing?\n"
        "Ana [00:12:11]: Lo tengo para fin de mes."
    )
    assert chunk.token_estimate == estimate_tokens(chunk.text)


# Four turns of 100 characters. One rendered line is 114 characters (~28 tokens),
# so a budget of 60 tokens fits two lines and not three.
FOUR_TURNS = [_turn(i, "x" * 100) for i in range(4)]


def test_starts_a_new_chunk_when_the_budget_is_exceeded():
    chunks = build_chunks(FOUR_TURNS, max_tokens=60)

    assert (chunks[0].turn_start, chunks[0].turn_end) == (0, 1)
    assert all(c.token_estimate <= 60 for c in chunks)
    covered = {i for c in chunks for i in range(c.turn_start, c.turn_end + 1)}
    assert covered == {0, 1, 2, 3}


def test_repeats_the_last_turn_of_a_chunk_as_the_first_of_the_next():
    chunks = build_chunks(FOUR_TURNS, max_tokens=60)

    assert [(c.turn_start, c.turn_end) for c in chunks] == [(0, 1), (1, 2), (2, 3)]
    assert [c.idx for c in chunks] == [0, 1, 2]


def test_keeps_an_oversized_turn_in_its_own_chunk_without_overlap():
    turns = [_turn(0, "x" * 100), _turn(1, "x" * 1000), _turn(2, "x" * 100)]

    chunks = build_chunks(turns, max_tokens=60)

    assert [(c.turn_start, c.turn_end) for c in chunks] == [(0, 0), (1, 1), (2, 2)]
    assert chunks[1].token_estimate > 60


def test_returns_no_chunks_for_no_turns():
    assert build_chunks([], max_tokens=60) == []


from app.chunking import render_numbered_turns


def test_numbered_rendering_carries_the_turn_index_the_model_must_cite():
    turns = [
        Turn(idx=0, speaker="Marco", start_seconds=724, text="Hola."),
        Turn(idx=1, speaker="Ana", start_seconds=3671, text="Dale."),
    ]

    assert render_numbered_turns(turns) == "#0 Marco [00:12:04]: Hola.\n#1 Ana [01:01:11]: Dale."

import pytest

from app.parsing import TranscriptParseError, parse_transcript


def test_parses_a_single_bracketed_turn():
    raw = "[00:12:04] Marco: Que hacemos con el rediseno de pricing?"

    turns = parse_transcript(raw)

    assert len(turns) == 1
    turn = turns[0]
    assert turn.idx == 0
    assert turn.speaker == "Marco"
    assert turn.start_seconds == 12 * 60 + 4
    assert turn.text == "Que hacemos con el rediseno de pricing?"


def test_accepts_minutes_seconds_timestamps():
    raw = "[12:04] Marco: Arrancamos."

    turns = parse_transcript(raw)

    assert turns[0].start_seconds == 12 * 60 + 4


def test_joins_continuation_lines_into_the_preceding_turn():
    raw = (
        "[00:12:04] Marco: Que hacemos con pricing?\n"
        "Va este trimestre o no?\n"
        "[00:12:11] Ana: Lo puedo tener para fin de mes."
    )

    turns = parse_transcript(raw)

    assert len(turns) == 2
    assert turns[0].text == "Que hacemos con pricing? Va este trimestre o no?"
    assert turns[1].speaker == "Ana"


@pytest.mark.parametrize(
    "raw",
    ["", "Notes from the meeting\nNobody labelled the speakers here."],
)
def test_raises_when_no_turn_can_be_recognised(raw):
    with pytest.raises(TranscriptParseError):
        parse_transcript(raw)


# The tests below lock in behaviour the parser already has. They are guards,
# not drivers: each one names a regression that would otherwise go unnoticed.


def test_keeps_colons_inside_the_utterance():
    turns = parse_transcript("[00:01:00] Marco: El plan es: shippear el viernes.")

    assert turns[0].speaker == "Marco"
    assert turns[0].text == "El plan es: shippear el viernes."


def test_skips_header_lines_before_the_first_turn():
    raw = (
        "Q4 Planning\n"
        "Date: 2026-09-01\n"
        "Attendees: Marco, Ana\n"
        "\n"
        "[00:00:05] Marco: Arrancamos."
    )

    turns = parse_transcript(raw)

    assert len(turns) == 1
    assert turns[0].text == "Arrancamos."


def test_numbers_turns_in_order_of_appearance():
    raw = "[00:00:01] Ana: uno\n[00:00:02] Marco: dos\n[00:00:03] Ana: tres"

    turns = parse_transcript(raw)

    assert [t.idx for t in turns] == [0, 1, 2]
    assert [t.speaker for t in turns] == ["Ana", "Marco", "Ana"]


def test_accepts_speaker_names_with_spaces_dots_and_accents():
    turns = parse_transcript("[00:00:01] Dr. Ana Pérez: Buenas.")

    assert turns[0].speaker == "Dr. Ana Pérez"


from datetime import date

from app.parsing import date_from_filename, parse_metadata


def test_reads_title_and_date_from_the_header_before_the_first_turn():
    raw = "Q4 Planning\nDate: 2026-09-01\nAttendees: Marco, Ana\n\n[00:00:04] Marco: Hi."

    meta = parse_metadata(raw)

    assert meta.title == "Q4 Planning"
    assert meta.date == date(2026, 9, 1)


def test_metadata_is_empty_when_the_transcript_starts_with_a_turn():
    meta = parse_metadata("[00:00:04] Marco: Hi.\nAttendees: nobody")

    assert (meta.title, meta.date) == (None, None)


def test_a_bad_date_line_is_ignored_rather_than_raised():
    assert parse_metadata("Sync\nDate: 2026-13-45\n[00:00:04] A: x").date is None


def test_date_from_filename_prefix():
    assert date_from_filename("2026-09-08-weekly-sync.txt") == date(2026, 9, 8)
    assert date_from_filename("weekly-sync.txt") is None

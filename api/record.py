"""Capture a real run into fixtures/test-mode.json, the file test mode replays.

Usage: uv run python record.py [--out PATH]

Reads the database the API uses (DATABASE_URL from api/.env, no model is
called): the context headers and extracted rows of every sample meeting, and
the latest stored trace for every golden question in each mode, classic
without the index and agentic. Refs are replaced by meeting titles on the way
out, so the recording survives being loaded into a fresh database in any
order. Run it after a seed and an eval of each mode, and whenever the
transcripts, the chunker or the golden set change; tests/test_recording.py
says when it is stale.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.chunking import build_chunks
from app.extraction import Extraction, ExtractedActionItem, ExtractedDecision
from app.models import Trace
from app.parsing import parse_transcript
from app.recorded import RECORDING_PATH, RecordedAnswer, RecordedMeeting, Recording, answer_from_trace
from app.settings import Settings

ROOT = Path(__file__).resolve().parent.parent
TRACE_COLUMNS = (
    "mode, question, model, answer, refused, citations, dropped_citations, retrieved,"
    " input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, cost_usd::float AS cost_usd,"
    " latency_ms, index_rows, tool_calls, rounds"
)


def record_meetings(conn: psycopg.Connection, titles: list[str]) -> dict[str, RecordedMeeting]:
    """One header per chunk and the extracted rows, for the newest ingest of each sample transcript."""
    recorded: dict[str, RecordedMeeting] = {}
    for title in titles:
        row = conn.execute(
            "SELECT id FROM meetings WHERE title = %s ORDER BY created_at DESC LIMIT 1", (title,)
        ).fetchone()
        if row is None:
            sys.exit(f"{title} is not in the database; run scripts/seed.sh with a key first")
        meeting_id = row["id"]
        headers = [
            r["context_header"]
            for r in conn.execute("SELECT context_header FROM chunks WHERE meeting_id = %s ORDER BY idx", (meeting_id,))
        ]
        if not headers or any(not h for h in headers):
            sys.exit(f"{title} has chunks without context headers; it was not ingested with a key")
        turns = parse_transcript((ROOT / "fixtures" / "transcripts" / f"{title}.txt").read_text(encoding="utf-8-sig"))
        if len(build_chunks(turns)) != len(headers):
            sys.exit(f"{title}: the database has {len(headers)} chunks but the transcript now cuts into"
                     f" {len(build_chunks(turns))}; re-ingest it before recording")
        decisions = [
            ExtractedDecision(statement=r["statement"], decided_by=r["decided_by"], turn=r["turn_idx"], confidence=r["confidence"])
            for r in conn.execute(
                "SELECT statement, decided_by, turn_idx, confidence FROM decisions WHERE meeting_id = %s ORDER BY turn_idx, id",
                (meeting_id,),
            )
        ]
        action_items = [
            ExtractedActionItem(
                task=r["task"], owner=r["owner"], due_text=r["due_text"],
                due_date=r["due_date"].isoformat() if r["due_date"] else None,
                status=r["status"], turn=r["turn_idx"], confidence=r["confidence"],
            )
            for r in conn.execute(
                "SELECT task, owner, due_text, due_date, status, turn_idx, confidence FROM action_items"
                " WHERE meeting_id = %s ORDER BY turn_idx, id",
                (meeting_id,),
            )
        ]
        recorded[title] = RecordedMeeting(headers=headers, extraction=Extraction(decisions=decisions, action_items=action_items))
    return recorded


def record_answers(conn: psycopg.Connection, golden: list[dict], outline_refs: dict[str, str]) -> list[RecordedAnswer]:
    """The latest trace per golden question and mode, with every ref turned into a title.

    Classic refs are numbered by retrieval order and are all present in the
    trace's retrieved list. Agentic refs follow the table of contents, so a
    search that found nothing can name a ref the trace never resolved; the
    outline order fills those in, and the trace's own refs must agree with it."""
    answers: list[RecordedAnswer] = []
    for q in golden:
        for mode in ("classic", "agentic"):
            extra = " AND index_rows = 0" if mode == "classic" else ""
            row = conn.execute(
                f"SELECT {TRACE_COLUMNS} FROM traces WHERE question = %s AND mode = %s{extra}"
                " ORDER BY created_at DESC LIMIT 1",
                (q["question"], mode),
            ).fetchone()
            if row is None:
                sys.exit(f"no {mode} trace for {q['id']!r}; run eval.py --mode {mode} first")
            trace = Trace(**row)
            seen = {c.ref: c.meeting_title for c in [*trace.retrieved, *trace.citations]}
            ref_titles = {**outline_refs, **seen} if mode == "agentic" else seen
            for ref, title in seen.items():
                if outline_refs.get(ref, title) != title and mode == "agentic":
                    sys.exit(f"{q['id']} ({mode}): {ref} was {title} when traced but is {outline_refs[ref]} now;"
                             " the meetings were re-ingested since, run the eval again")
            answers.append(answer_from_trace(trace, ref_titles=ref_titles, question_type=q["type"]))
    return answers


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=RECORDING_PATH)
    args = parser.parse_args()

    golden = json.loads((ROOT / "fixtures" / "golden.json").read_text(encoding="utf-8"))["questions"]
    titles = sorted(path.stem for path in (ROOT / "fixtures" / "transcripts").glob("*.txt"))
    with psycopg.connect(Settings().database_url, row_factory=dict_row) as conn:
        outline = [r["title"] for r in conn.execute("SELECT title FROM meetings ORDER BY meeting_date NULLS LAST, title")]
        outline_refs = {f"M{i + 1}": title for i, title in enumerate(outline)}
        meetings = record_meetings(conn, titles)
        answers = record_answers(conn, golden, outline_refs)
    recording = Recording(recorded_at=date.today().isoformat(), meetings=meetings, answers=answers)
    args.out.write_text(recording.model_dump_json(indent=1) + "\n", encoding="utf-8")

    rows = sum(len(m.extraction.decisions) + len(m.extraction.action_items) for m in meetings.values())
    refused = sum(a.refused for a in answers)
    print(f"{args.out}: {len(meetings)} meetings, {rows} extracted rows,"
          f" {len(answers)} answers ({refused} refusals) for {len(golden)} questions")


if __name__ == "__main__":
    main()

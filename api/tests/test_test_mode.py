"""Test mode through the API: the recording loads the sample meetings and answers the sample questions."""

import psycopg

from app.recorded import REPLAY_MODEL, load_recording
from tests.test_api import _events

RECORDING = load_recording()
TITLES = sorted(RECORDING.meetings)
QUESTION = "Who leads the pricing page redesign?"


def _load_samples(client):
    return client.post("/meetings/samples")


def test_status_reports_no_key_no_samples_and_the_sample_questions(client_without_llm):
    response = client_without_llm.get("/test-mode")

    assert response.status_code == 200
    body = response.json()
    assert body["has_key"] is False
    assert body["samples"] == {"loaded": [], "missing": TITLES}
    assert len(body["questions"]) == 23
    assert body["questions"][0] == {"question": QUESTION, "type": "lookup"}


def test_status_reports_a_key_when_answering_is_configured(client):
    assert client.get("/test-mode").json()["has_key"] is True


def test_loading_the_samples_ingests_the_five_meetings_from_the_recording(client_without_llm, test_db_url):
    response = _load_samples(client_without_llm)

    assert response.status_code == 200
    body = response.json()
    assert [m["title"] for m in body["loaded"]] == TITLES
    assert body["skipped"] == []
    assert all(m["turn_count"] >= 25 and m["chunk_count"] >= 2 for m in body["loaded"])
    assert sum(m["decisions"] + m["action_items"] for m in body["loaded"]) == 69
    assert client_without_llm.get("/test-mode").json()["samples"] == {"loaded": TITLES, "missing": []}
    # Each sample commits on its own, so they carry distinct timestamps and list newest first in load order.
    listed = client_without_llm.get("/meetings").json()
    assert [m["title"] for m in listed] == list(reversed(TITLES))
    assert len({m["created_at"] for m in listed}) == 5
    with psycopg.connect(test_db_url) as conn:
        header = conn.execute(
            "SELECT c.context_header FROM chunks c JOIN meetings m ON m.id = c.meeting_id WHERE m.title = %s AND c.idx = 0",
            (TITLES[0],),
        ).fetchone()[0]
    assert header == RECORDING.meetings[TITLES[0]].headers[0]


def test_loading_the_samples_again_skips_the_ones_already_there(client_without_llm):
    _load_samples(client_without_llm)

    body = _load_samples(client_without_llm).json()

    assert body == {"loaded": [], "skipped": TITLES}
    assert len(client_without_llm.get("/meetings").json()) == 5


def test_the_samples_come_from_the_recording_even_with_a_key(client, test_db_url):
    """With a key, the fakes stand in for Claude here; the recording must still win over them."""
    body = _load_samples(client).json()

    assert sum(m["decisions"] + m["action_items"] for m in body["loaded"]) == 69
    with psycopg.connect(test_db_url) as conn:
        headers = {r[0] for r in conn.execute("SELECT context_header FROM chunks")}
    assert headers <= {h for m in RECORDING.meetings.values() for h in m.headers}


def test_ask_in_test_mode_replays_the_recorded_agentic_answer_through_the_real_pipeline(client_without_llm, test_db_url):
    _load_samples(client_without_llm)

    response = client_without_llm.post("/ask", json={"question": QUESTION, "mode": "agentic", "test_mode": True})

    assert response.status_code == 200
    body = response.json()
    assert body["model"] == REPLAY_MODEL
    assert body["cost_usd"] == 0
    assert body["mode"] == "agentic"
    assert body["answer"].startswith("Ana")
    assert body["citations"] and body["dropped_citations"] == 0
    assert {c["meeting_title"] for c in body["citations"]} <= set(TITLES)
    assert all(c["text"] for c in body["citations"])
    assert body["tool_calls"] and body["rounds"] >= 1
    assert body["input_tokens"] > 0
    with psycopg.connect(test_db_url) as conn:
        assert conn.execute("SELECT model FROM traces").fetchall() == [(REPLAY_MODEL,)]


def test_ask_in_test_mode_replays_the_recorded_classic_answer(client_without_llm):
    _load_samples(client_without_llm)

    body = client_without_llm.post("/ask", json={"question": "who leads the pricing page redesign", "test_mode": True}).json()

    assert body["model"] == REPLAY_MODEL
    assert body["mode"] == "classic"
    assert body["answer"].startswith("Ana leads the pricing page redesign.")
    assert body["retrieved"]  # retrieval is real, even in test mode


def test_ask_in_test_mode_replays_a_recorded_refusal(client_without_llm):
    _load_samples(client_without_llm)

    body = client_without_llm.post("/ask", json={"question": "What was revenue in September?", "test_mode": True}).json()

    assert body["refused"] is True
    assert body["citations"] == []
    assert "[[none]]" not in body["answer"]


def test_ask_in_test_mode_only_knows_the_sample_questions(client_without_llm, test_db_url):
    _load_samples(client_without_llm)

    response = client_without_llm.post("/ask", json={"question": "What colour is the logo?", "test_mode": True})

    assert response.status_code == 422
    assert "sample questions" in response.json()["detail"]
    with psycopg.connect(test_db_url) as conn:
        assert conn.execute("SELECT count(*) FROM traces").fetchone()[0] == 0


def test_ask_in_test_mode_needs_the_samples_loaded_first(client_without_llm):
    response = client_without_llm.post("/ask", json={"question": QUESTION, "test_mode": True})

    assert response.status_code == 409
    assert "sample meetings" in response.json()["detail"]


def test_ask_without_a_key_points_at_test_mode(client_without_llm):
    response = client_without_llm.post("/ask", json={"question": QUESTION})

    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]
    assert "test mode" in response.json()["detail"].lower()


def test_ask_stream_in_test_mode_sends_each_replayed_tool_call_then_the_answer(client_without_llm):
    _load_samples(client_without_llm)

    response = client_without_llm.post("/ask/stream", json={"question": QUESTION, "mode": "agentic", "test_mode": True})

    assert response.status_code == 200
    events = _events(response)
    names = [name for name, _ in events]
    assert names[:-1] and set(names[:-1]) == {"tool_call"}
    assert names[-1] == "answer"
    assert events[0][1]["name"] == "read_turns"
    assert events[-1][1]["model"] == REPLAY_MODEL
    assert events[-1][1]["dropped_citations"] == 0


def test_ask_stream_in_test_mode_rejects_an_unknown_question_before_streaming(client_without_llm):
    _load_samples(client_without_llm)

    response = client_without_llm.post("/ask/stream", json={"question": "What colour is the logo?", "test_mode": True})

    assert response.status_code == 422

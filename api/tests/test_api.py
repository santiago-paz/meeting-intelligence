"""API tests. They run against the test database (see conftest.client)."""

from uuid import uuid4

import psycopg

TRANSCRIPT = b"[00:12:04] Marco: Arrancamos.\n[00:12:11] Ana: Dale."


def _upload(client, content: bytes = TRANSCRIPT, filename: str = "q4-planning.txt"):
    return client.post("/meetings", files={"file": (filename, content, "text/plain")})


def test_health_reports_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_meeting_stores_it_and_returns_id_and_counts(client):
    response = _upload(client)

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "q4-planning"
    assert body["turn_count"] == 2
    assert body["chunk_count"] == 1
    assert "turns" not in body
    assert body["id"]


def test_create_meeting_rejects_a_file_with_no_speaker_turns(client):
    response = _upload(client, b"Just some notes.\nNo speaker labels anywhere.", "notes.txt")

    assert response.status_code == 422
    assert "No speaker turns found" in response.json()["detail"]


def test_create_meeting_accepts_a_utf8_file_with_a_bom(client):
    response = _upload(client, b"\xef\xbb\xbf[00:12:04] Marco: Hola.")

    assert response.status_code == 200
    assert response.json()["turn_count"] == 1


def test_create_meeting_rejects_a_file_that_is_not_utf8(client):
    response = _upload(client, b"[00:12:04] Marco: caf\xe9")  # latin-1 e-acute, invalid as UTF-8

    assert response.status_code == 422
    assert "UTF-8" in response.json()["detail"]


def test_get_meeting_returns_its_turns(client):
    meeting_id = _upload(client).json()["id"]

    response = client.get(f"/meetings/{meeting_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "q4-planning"
    assert [t["speaker"] for t in body["turns"]] == ["Marco", "Ana"]
    assert body["turns"][1]["start_seconds"] == 12 * 60 + 11


def test_list_meetings_newest_first_with_turn_counts(client):
    _upload(client, filename="first.txt")
    _upload(client, b"[00:00:01] Ana: Sola.", filename="second.txt")

    response = client.get("/meetings")

    assert response.status_code == 200
    assert [(m["title"], m["turn_count"]) for m in response.json()] == [("second", 1), ("first", 2)]


def test_get_unknown_meeting_is_404(client):
    response = client.get(f"/meetings/{uuid4()}")

    assert response.status_code == 404


def test_create_meeting_stores_a_context_header_and_an_embedding_per_chunk(client, test_db_url):
    meeting_id = _upload(client).json()["id"]

    with psycopg.connect(test_db_url) as conn:
        rows = conn.execute(
            "SELECT context_header, embedding IS NOT NULL FROM chunks"
            " WHERE meeting_id = %s ORDER BY idx",
            (meeting_id,),
        ).fetchall()

    assert rows == [("Context for chunk 0", True)]


def test_create_meeting_without_an_anthropic_key_is_a_clear_503(client_without_llm):
    response = _upload(client_without_llm)

    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]


def _ask(client, question: str, canned_answer: str):
    from app.main import app, get_answerer
    from tests.fakes import FakeAnswerer

    app.dependency_overrides[get_answerer] = lambda: FakeAnswerer(canned_answer)
    return client.post("/ask", json={"question": question})


def test_ask_answers_with_resolved_citations_and_counts_the_dropped_ones(client, test_db_url):
    _upload(client)

    response = _ask(
        client,
        "Who started the meeting?",
        "Marco opened it. [[M1#0]] Ana agreed. [[M1#1]] Bogus. [[M1#9]] [[M7#1]]",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Marco opened it. [[M1#0]] Ana agreed. [[M1#1]] Bogus."
    assert [(c["speaker"], c["timestamp"], c["turn"]) for c in body["citations"]] == [
        ("Marco", "00:12:04", 0),
        ("Ana", "00:12:11", 1),
    ]
    assert body["dropped_citations"] == 2
    assert body["refused"] is False
    assert body["mode"] == "classic"
    assert [r["ref"] for r in body["retrieved"]] == ["M1"]
    assert body["trace_id"]
    with psycopg.connect(test_db_url) as conn:
        assert conn.execute("SELECT count(*) FROM traces").fetchone()[0] == 1


def test_ask_reports_a_refusal_when_the_model_finds_nothing(client):
    _upload(client)

    body = _ask(client, "How many people are we hiring?", "The meetings do not cover hiring. [[none]]").json()

    assert body["refused"] is True
    assert body["citations"] == []
    assert body["answer"] == "The meetings do not cover hiring."


def test_ask_without_an_anthropic_key_is_a_clear_503(client_without_llm):
    response = client_without_llm.post("/ask", json={"question": "Anything at all?"})

    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]


def test_ask_rejects_an_empty_question(client):
    assert client.post("/ask", json={"question": ""}).status_code == 422

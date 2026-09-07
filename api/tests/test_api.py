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


WITH_HEADER = (
    b"Weekly Sync\nDate: 2026-09-08\nAttendees: Marco, Ana\n\n"
    b"[00:12:04] Marco: Arrancamos.\n[00:12:11] Ana: Dale, yo mando los mockups."
)


def _extracting(client_app, decisions=(), action_items=()):
    from app.extraction import Extraction
    from app.main import get_extractor
    from tests.fakes import FakeExtractor

    client_app.dependency_overrides[get_extractor] = lambda: FakeExtractor(
        Extraction(decisions=list(decisions), action_items=list(action_items))
    )


def test_create_meeting_stores_extracted_rows_and_counts_the_discarded_ones(client):
    from app.extraction import ExtractedActionItem, ExtractedDecision
    from app.main import app

    _extracting(
        app,
        decisions=[
            ExtractedDecision(statement="We start now.", decided_by="Marco", turn=0, confidence=0.9),
            ExtractedDecision(statement="Ghost.", decided_by="Marco", turn=9, confidence=0.9),
        ],
        action_items=[
            ExtractedActionItem(task="Send the mockups.", owner="Ana", due_text="today",
                                due_date="2026-09-08", status="open", turn=1, confidence=0.8),
        ],
    )

    body = _upload(client, WITH_HEADER).json()

    assert (body["decisions"], body["action_items"], body["discarded"]) == (1, 1, 1)
    detail = client.get(f"/meetings/{body['id']}").json()
    assert detail["meeting_date"] == "2026-09-08"
    assert detail["decisions"] == [{"statement": "We start now.", "decided_by": "Marco", "turn": 0, "confidence": 0.9}]
    assert detail["action_items"][0]["owner"] == "Ana"
    assert detail["action_items"][0]["due_date"] == "2026-09-08"


def test_meeting_date_falls_back_to_the_filename_and_then_to_nothing(client):
    dated = _upload(client, filename="2026-09-01-q4.txt").json()
    undated = _upload(client, filename="meeting.txt").json()

    assert client.get(f"/meetings/{dated['id']}").json()["meeting_date"] == "2026-09-01"
    assert client.get(f"/meetings/{undated['id']}").json()["meeting_date"] is None


def test_ask_shows_the_extracted_index_to_the_model(client):
    from app.extraction import ExtractedDecision
    from app.main import app, get_answerer
    from tests.fakes import FakeAnswerer

    _extracting(app, decisions=[ExtractedDecision(statement="We start now.", decided_by="Marco", turn=0, confidence=0.9)])
    _upload(client, WITH_HEADER)
    fake = FakeAnswerer("We start now. [[M1#0]]")
    app.dependency_overrides[get_answerer] = lambda: fake

    body = client.post("/ask", json={"question": "What did we decide?", "use_index": True}).json()

    prompt = fake.prompts[0]
    assert "<index>" in prompt
    assert '[[M1#0]] Decision (Marco): We start now.' in prompt
    assert 'date="2026-09-08"' in prompt
    assert body["index_rows"] == 1
    assert body["citations"][0]["turn"] == 0


def test_ask_can_leave_the_index_out_so_the_two_prompts_can_be_compared(client):
    from app.extraction import ExtractedDecision
    from app.main import app, get_answerer
    from tests.fakes import FakeAnswerer

    _extracting(app, decisions=[ExtractedDecision(statement="We start now.", decided_by="Marco", turn=0, confidence=0.9)])
    _upload(client, WITH_HEADER)
    fake = FakeAnswerer("We start now. [[M1#0]]")
    app.dependency_overrides[get_answerer] = lambda: fake

    body = client.post("/ask", json={"question": "What did we decide?", "use_index": False}).json()

    assert "<index>" not in fake.prompts[0]
    assert body["index_rows"] == 0


def test_classic_mode_leaves_the_index_out_by_default(client):
    from app.extraction import ExtractedDecision
    from app.main import app, get_answerer
    from tests.fakes import FakeAnswerer

    _extracting(app, decisions=[ExtractedDecision(statement="We start now.", decided_by="Marco", turn=0, confidence=0.9)])
    _upload(client, WITH_HEADER)
    fake = FakeAnswerer("We start now. [[M1#0]]")
    app.dependency_overrides[get_answerer] = lambda: fake

    body = client.post("/ask", json={"question": "What did we decide?"}).json()

    assert "<index>" not in fake.prompts[0]
    assert body["index_rows"] == 0


def _agent(text: str, actions=()):
    from app.main import app, get_agent
    from tests.fakes import FakeAgent

    agent = FakeAgent(text, actions)
    app.dependency_overrides[get_agent] = lambda: agent
    return agent


def test_agentic_mode_cites_only_turns_its_tools_read(client):
    _upload(client)
    agent = _agent("Marco opened. [[M1#0]] Ana agreed. [[M1#1]]",
                   actions=[("read_turns", {"meeting_ref": "M1", "start": 0, "end": 0})])

    body = client.post("/ask", json={"question": "Who spoke?", "mode": "agentic"}).json()

    assert body["mode"] == "agentic"
    assert [c["turn"] for c in body["citations"]] == [0], "turn 1 was never read, so it cannot be cited"
    assert body["dropped_citations"] == 1
    assert body["rounds"] == 1
    assert body["tool_calls"][0]["name"] == "read_turns" and body["tool_calls"][0]["summary"] == "M1 turns 0-0"
    assert [(r["ref"], r["turn_start"], r["turn_end"], r["similarity"]) for r in body["retrieved"]] == [("M1", 0, 0, None)]
    index_block = agent.systems[0][1]
    assert "<index>" in index_block["text"] and index_block["cache_control"] == {"type": "ephemeral"}


def test_agentic_search_tool_returns_excerpts_the_model_can_cite(client):
    _upload(client)
    _agent("Ana agreed. [[M1#1]]", actions=[("search_transcripts", {"query": "agree", "meeting_ref": None})])

    body = client.post("/ask", json={"question": "Did Ana agree?", "mode": "agentic"}).json()

    assert [c["turn"] for c in body["citations"]] == [1]
    assert body["tool_calls"][0]["summary"] == "1 excerpt(s) for 'agree'"
    assert body["retrieved"][0]["similarity"] is not None


def test_agentic_tool_errors_are_recorded_and_the_answer_still_comes_back(client):
    _upload(client)
    _agent("Nothing there. [[none]]", actions=[("read_turns", {"meeting_ref": "M9", "start": 0, "end": 3})])

    body = client.post("/ask", json={"question": "Anything?", "mode": "agentic"}).json()

    assert body["refused"] is True
    assert body["tool_calls"][0]["summary"].startswith("error: unknown meeting ref M9")


def test_agentic_mode_without_an_anthropic_key_is_a_clear_503(client_without_llm):
    response = client_without_llm.post("/ask", json={"question": "Anything at all?", "mode": "agentic"})

    assert response.status_code == 503

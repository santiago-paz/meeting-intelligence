from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_meeting_returns_turns_for_an_uploaded_transcript():
    content = b"[00:12:04] Marco: Arrancamos.\n[00:12:11] Ana: Dale."

    response = client.post(
        "/meetings",
        files={"file": ("meeting.txt", content, "text/plain")},
    )

    assert response.status_code == 201
    turns = response.json()["turns"]
    assert [t["speaker"] for t in turns] == ["Marco", "Ana"]
    assert turns[0]["idx"] == 0
    assert turns[1]["start_seconds"] == 12 * 60 + 11


def test_health_reports_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_meeting_rejects_a_file_with_no_speaker_turns():
    content = b"Just some notes.\nNo speaker labels anywhere."

    response = client.post(
        "/meetings",
        files={"file": ("notes.txt", content, "text/plain")},
    )

    assert response.status_code == 422
    assert "No speaker turns found" in response.json()["detail"]


def test_create_meeting_accepts_a_utf8_file_with_a_bom():
    content = b"\xef\xbb\xbf[00:12:04] Marco: Hola."

    response = client.post(
        "/meetings",
        files={"file": ("meeting.txt", content, "text/plain")},
    )

    assert response.status_code == 201
    assert response.json()["turns"][0]["speaker"] == "Marco"


def test_create_meeting_rejects_a_file_that_is_not_utf8():
    content = b"[00:12:04] Marco: caf\xe9"  # latin-1 e-acute, invalid as UTF-8

    response = client.post(
        "/meetings",
        files={"file": ("meeting.txt", content, "text/plain")},
    )

    assert response.status_code == 422
    assert "UTF-8" in response.json()["detail"]

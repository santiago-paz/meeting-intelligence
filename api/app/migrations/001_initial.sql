-- Meetings, their speaker turns, and the chunks cut from them.
-- Embeddings and the extracted rows arrive in later migrations.

CREATE TABLE meetings (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title           text NOT NULL,
    source_filename text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE turns (
    meeting_id    uuid NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    idx           integer NOT NULL,
    speaker       text NOT NULL,
    start_seconds integer NOT NULL,
    text          text NOT NULL,
    PRIMARY KEY (meeting_id, idx)
);

CREATE TABLE chunks (
    meeting_id     uuid NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    idx            integer NOT NULL,
    turn_start     integer NOT NULL,
    turn_end       integer NOT NULL,
    text           text NOT NULL,
    token_estimate integer NOT NULL,
    PRIMARY KEY (meeting_id, idx),
    CHECK (turn_start <= turn_end)
);

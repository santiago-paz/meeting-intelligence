-- Decisions and action items extracted from each transcript, each anchored to
-- the turn it was said in. The composite foreign key makes the database itself
-- refuse a row that points at a turn that does not exist. The meeting date is
-- what due dates resolve against.
ALTER TABLE meetings ADD COLUMN meeting_date date;

CREATE TABLE decisions (
    id          bigserial PRIMARY KEY,
    meeting_id  uuid NOT NULL,
    statement   text NOT NULL,
    decided_by  text,
    turn_idx    integer NOT NULL,
    confidence  real NOT NULL,
    FOREIGN KEY (meeting_id, turn_idx) REFERENCES turns (meeting_id, idx) ON DELETE CASCADE
);

CREATE TABLE action_items (
    id          bigserial PRIMARY KEY,
    meeting_id  uuid NOT NULL,
    task        text NOT NULL,
    owner       text,
    due_text    text,
    due_date    date,
    status      text NOT NULL DEFAULT 'open',
    turn_idx    integer NOT NULL,
    confidence  real NOT NULL,
    FOREIGN KEY (meeting_id, turn_idx) REFERENCES turns (meeting_id, idx) ON DELETE CASCADE
);

ALTER TABLE traces ADD COLUMN index_rows integer NOT NULL DEFAULT 0;

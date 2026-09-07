-- Agentic answers record every tool call and the number of rounds they took.
ALTER TABLE traces
    ADD COLUMN tool_calls jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN rounds integer NOT NULL DEFAULT 0;

-- One row per answered question: what was asked, what came back, what it
-- cost, and what the model was shown. The traces page reads these; the eval
-- runner gets the same data from the /ask response.
CREATE TABLE traces (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at         timestamptz NOT NULL DEFAULT now(),
    mode               text NOT NULL,
    question           text NOT NULL,
    model              text NOT NULL,
    answer             text NOT NULL,
    refused            boolean NOT NULL,
    citations          jsonb NOT NULL,
    dropped_citations  integer NOT NULL,
    retrieved          jsonb NOT NULL,
    input_tokens       integer NOT NULL,
    output_tokens      integer NOT NULL,
    cache_read_tokens  integer NOT NULL,
    cache_write_tokens integer NOT NULL,
    cost_usd           numeric(10, 6) NOT NULL,
    latency_ms         integer NOT NULL
);

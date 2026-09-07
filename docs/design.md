# Meeting Intelligence - design

Take-home assignment for NewPage, option 3: a system that answers questions about
meeting transcripts, including what was discussed, what was decided and who owes
what. Transcripts are text files with speaker labels and timestamps.

Timebox: one weekend, about 15 hours. Every cut below follows from that.

## Why transcripts break plain RAG

Chunk-and-embed works on PDFs and fails on transcripts in four specific ways.

1. The unit of meaning is a speaker turn, not a fixed number of tokens. Cutting
   mid-turn loses who said what.
2. Turns are not self-contained. "Yeah, let's do that by Friday" embeds to
   nothing useful, and half of any transcript looks like that.
3. The questions people ask are aggregations, not lookups: "what did we
   decide?", "what are my open action items?", "did the deadline move?". Top-k
   similarity search cannot answer these, no matter how good the reranker is.
4. Speaker and time are filters, not prose. "What did Marco say about budget in
   September" is a metadata query wearing a semantic query's clothes.

The design below answers those four points.

## Architecture

Two services and a database, all in Docker Compose.

The web service is Next.js 16 (App Router, Tailwind 4). It owns the UI and
nothing else. Its route handlers forward requests to the API.

The api service is FastAPI. It owns parsing, chunking, embedding, extraction,
retrieval, answering, evaluation and traces, and it is the only process that
talks to Postgres.

The db service is Postgres with pgvector. One store holds both the vectors and
the structured rows, so filters and joins come for free and there is no second
system to keep in sync.

Boundary rule: Python owns everything about AI, TypeScript owns pixels. The web
app could be replaced by a CLI without touching retrieval.

Traffic between them takes three shapes. Uploads and other writes go through a
Next route handler that forwards to the API, so the browser never sees the API
and there is no CORS. Reads (meeting list, transcript viewer) happen in server
components. The chat streams: the Next handler forwards the API's server-sent
events without buffering, and the last event carries the citations and a trace
id.

## Data model

```
meetings(id, title, source_filename, created_at)
turns(meeting_id, idx, speaker, start_seconds, text)
chunks(meeting_id, idx, turn_start, turn_end, text, token_estimate,
       context_header, embedding)
decisions(id, meeting_id, statement, decided_by, turn_idx, confidence)
action_items(id, meeting_id, task, owner, due_text, due_date, status,
             turn_idx, confidence)
traces(id, question, mode, retrieved, tool_calls, tokens, latency_ms,
       cost_usd, answer, citations)
```

Every extracted row carries the turn it came from. That column is what makes a
citation checkable instead of decorative.

Schema changes are numbered SQL files under `api/app/migrations`. A small
runner applies them in order at startup and records each one. Queries are plain
SQL through psycopg. The schema has six tables and one interesting query
(vector similarity with a filter). An ORM would hide that query, so there is
none.

## Ingest

`POST /meetings` takes a transcript file and runs these steps.

1. Parse into turns. Deterministic, no model. A line like
   `[HH:MM:SS] Speaker: text` or `[MM:SS] Speaker: text` starts a turn. A line
   without a timestamp continues the turn above it, and anything before the
   first turn (title, date, attendees) is ignored. A file with no turn at all
   gets a 422, because a parser that guesses pollutes the database silently.
2. Chunk: windows of whole consecutive turns, about 500 tokens each. Each window
   shares one turn with the next, so a question and its answer land together at
   least once. A turn longer than the budget becomes a chunk on its own. The
   rendered text keeps `Speaker [HH:MM:SS]:` on every line, because the speaker
   is information, not metadata.
3. Context header: one cheap model call per chunk (claude-haiku-4-5) writes a
   sentence that places the chunk inside the meeting. The whole transcript sits
   in the prompt as cached data, and the first chunk runs alone so the cache is
   warm before the rest fan out; fired all at once, every call would miss it.
   The header goes in front of the chunk before embedding. It is what makes
   "yeah, by Friday" retrievable. Without an API key the upload answers 503
   rather than storing chunks that would retrieve badly.
4. Embed the header plus chunk with a local model, BAAI/bge-small-en-v1.5
   through ONNX on CPU (384 dimensions). Anthropic does not ship an embeddings
   endpoint, and a second vendor key would make the demo harder to run for no
   gain at this corpus size. The embedder sits behind a two-method interface,
   so a hosted model such as Voyage is a swap plus one migration for the
   vector width. Vectors are written as pgvector text literals, which keeps
   the driver free of adapter registration.
5. Extract decisions and action items from the full transcript with structured
   output (claude-opus-5). Two rules in the prompt carry most of the value: a
   row must point at the turn where it was said, or be left out; and mentioning
   a task is not the same as owning it, so `owner` may be null.
6. Check the rows in code, not in the model. The turn must exist, the owner
   must be a speaker or a mentioned name or null, and `due_text` resolves
   against the meeting date. Rows that fail are dropped and counted.
7. Return `{id, title, turn_count, chunk_count, decisions, action_items,
   discarded}`. The UI shows `discarded`.

## Query path: two modes

`POST /ask` takes a question and a `mode`. Both modes share the index builder,
the two retrieval functions, the answer schema, the citation check and the
trace writer. The difference is who decides what the model reads.

In classic mode the system decides. Embed the question, take the top 8 chunks,
append every extracted row (about 40 rows at this corpus size, roughly 1.5k
tokens), make one model call, check the citations, answer. One call,
predictable, about three seconds. Its weakness is that the evidence is chosen
before the model knows what it needs. If the answer lives in two meetings and
the top 8 came from one, there is no way to ask for more.

In agentic mode the model decides. The system prompt carries an index (each
meeting with title, date, speakers and a one-paragraph summary, plus every
decision and action item with its turn id), cached between questions. The
model gets two tools, `search_transcripts(query, meeting?)` and
`read_turns(meeting, start, end)`, and the SDK's tool runner loops for at most
five rounds. "What did we decide?" is answered from the index with no tool
call. "What exactly did Ana say about legal?" takes a search and maybe a read.
Its weaknesses are latency, cost and the extra ways it can fail. Tool calls
stream to the UI, so the wait reads as work.

Both modes exist because the comparison is the interesting result. The eval
runs the same golden set in both modes and prints one table. Classic should win
on plain lookups; agentic should win on lists and on questions that span
meetings. The README reports what happened.

There is no query router. At this corpus size the extracted layer fits in the
prompt whole, so a router would only add a way to be wrong. The threshold where
one becomes necessary is documented, not built.

## Guardrails

In order of value:

1. The code checks every citation. Each `turn_id` the model returns must exist
   and must belong to something the model was shown: a retrieved chunk, a tool
   result, or the index. Claims that fail are flagged in the UI, not hidden.
2. Retrieved content is wrapped in delimiters, and the system prompt says it is
   data from a meeting, never an instruction. Transcripts are untrusted input:
   someone in a meeting can say "ignore your previous instructions".
3. Refuse outside the corpus. The golden set includes unanswerable questions so
   this can be measured.

## Evaluation

A golden set of 22 questions in `fixtures/golden.json`, written before the
retriever. Each answerable question lists the turns that support it, with a
verbatim quote that a test checks against the transcripts, plus the atomic
facts a complete answer states and the propositions a correct answer must
never assert. Types: lookup, aggregation, temporal, speaker-scoped, an
injection attempt spoken inside a meeting, a distractor, and unanswerable
questions that must be refused. `eval.py` prints, per mode: key-fact
completeness and faithfulness against cited turns (an LLM judge), coverage of
the golden turns by what was fetched, refusal precision and recall, latency
and cost per question.

Unit tests cover the deterministic parts (parser, chunker, citation check).
Storage and API tests run against the Postgres from Compose and are skipped
when `DATABASE_URL` is not set. They use a sibling database, `meetings_test`,
recreated from an empty schema for every test, so development data is never
touched.

## Observability

Every question writes a row to `traces`: mode, what was retrieved or which tools
ran with what arguments, tokens in and out, latency per stage, cost, the answer
and its citations. A `/traces` page in the web app reads them. Self-built, about
150 lines, because the point is to show the reasoning rather than to install a
vendor.

## Out of scope

Reranking, authentication, multiple users, incremental re-indexing, and the
voice bonus. The parser sits behind a small interface, so a Whisper adapter
would be about an hour of work later. The README names all of these as next
steps.

## Decisions

- 2026-09-06. Two-layer index (chunks plus extracted rows) over pure RAG,
  because the aggregation questions are the ones people ask. No router.
- 2026-09-06. Next.js plus FastAPI, with Python owning everything about AI. Two
  services cost about two hours of plumbing in a fifteen-hour budget, but the
  split mirrors how AI teams run and each side uses the language it is best at.
- 2026-09-06. No orchestration framework (LangChain, LlamaIndex). The pipeline
  is small enough that owning it costs less than abstracting it. The Anthropic
  SDK's tool runner drives the agentic loop.
- 2026-09-07. Two query modes, classic and agentic, after reading Anthropic's
  guidance on progressive disclosure (show the model an index, let it fetch
  details). Classic is the degenerate case of agentic, so both together cost
  about one extra hour and buy a measured comparison.
- 2026-09-07. Plain SQL through psycopg with numbered migration files, no ORM.
  Storage tests hit the real database from Compose.
- 2026-09-07. Local embeddings (bge-small via fastembed) over Voyage or OpenAI:
  one credential to run the whole demo, quality that is enough for five
  meetings, and a documented swap path. Model-backed services are injected as
  dependencies so the test suite runs offline against fakes; the embedder loads
  on first use so tests never pull the model.

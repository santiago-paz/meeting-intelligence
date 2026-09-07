# Meeting Intelligence

Upload meeting transcripts, then ask what was discussed, decided and assigned.
Every claim in an answer points at the turn it comes from, and the code checks
that pointer before the answer reaches the screen.

This is my take-home for NewPage (option 3), done in a weekend. I built it
on two layers: turn-aware chunks with embeddings for search, plus the
decisions and action items extracted from each transcript, each anchored to
the turn where it was said. Questions can be answered in two ways, and the
same eval runs against both, so I can choose between them on numbers I can
show.

The brief asked seven questions. They come first, in its order. After them:
what the app does page by page, how a question is answered step by step, the
measured numbers, and the layout of the repo.

## 1. Quick setup

You need Docker, Python 3.13 with [uv](https://docs.astral.sh/uv/), Node 20 or
newer, and an Anthropic API key. The key is optional: without one, test mode
replays a recorded run (see the end of this section).

1. Start Postgres with pgvector:

   ```bash
   docker compose up -d db
   ```

2. Configure the API. Copy `api/.env.example` to `api/.env` and put your key
   in `ANTHROPIC_API_KEY`. Then start it:

   ```bash
   cd api && uv sync && uv run uvicorn app.main:app --port 8000
   ```

   The first request downloads a small embedding model (ONNX, runs on CPU).

3. Load the five sample meetings:

   ```bash
   scripts/seed.sh
   ```

   Without a key, skip this step. The Meetings page has a button that loads
   the same five transcripts from the recorded run.

4. Start the web app:

   ```bash
   cd web && npm install && npm run dev
   ```

5. Open http://localhost:3000.

Without the key, uploads and live questions answer 503 with a message that
says what is missing, and the app offers test mode instead. The Meetings page
loads the five sample meetings from a recorded run, and the Ask page has a
Test mode switch, on by default when the API has no key, that replays the
answers Claude gave to the 23 golden questions. Nothing is spent. With a key,
the same switch shows the recorded answers for free. On the sample corpus a
live question costs between three and eleven cents; the traces page shows
the exact figure for each one.

To check the install, run `uv run pytest` in `api/` and `npm test` in `web/`.
Neither needs a key; the API's storage tests use the database from step 1.
The eval commands are under [Tests and evaluation](#tests-and-evaluation).

## 2. Architecture overview

Two services, one database and one external API. Everything about AI lives
in Python; TypeScript owns pixels. The web app could be replaced by a CLI
without touching retrieval.

```
browser
   |
   v
web    Next.js 16, App Router                                   port 3000
       pages: meetings, ask, traces
       route handlers forward uploads and the answer stream to the API,
       server components read from it, the browser never talks to the API
   |
   v
api    FastAPI, Python 3.13                                     port 8000
       ingest   parse -> chunk -> context headers + extraction -> embed
                -> check the rows -> store, in one transaction
       answer   classic: embed the question, top 8 chunks, one model call
                agentic: table of contents + search_transcripts / read_turns,
                         up to 5 tool rounds
       both     citation check -> cost -> trace
   |                       |                         |
   v                       v                         v
db                        Anthropic API              bge-small-en-v1.5
Postgres 17 + pgvector    Haiku 4.5  context headers ONNX on CPU, in-process
HNSW index on chunks      Opus 5     extraction,     384-dimension vectors
meetings, turns, chunks,             answers, agent
decisions, action_items,  Sonnet 5   eval judge
traces
```

The web service owns the pages and nothing else. Uploads and questions go
through a Next route handler that forwards to the API, reads happen in
server components, and the answer arrives as server-sent events that the
handler passes through without buffering; the last event carries the
citations and a trace id.

The API owns parsing, chunking, context headers, embeddings, extraction,
retrieval, answering, the citation check, traces and the eval, and it is the
only process that talks to Postgres. Every model-backed piece (header writer,
extractor, answerer, agent, embedder) sits behind a small interface, which is
what lets the tests run without a key and lets test mode replay a recording
through the same pipeline.

One Postgres holds both the vectors and the structured rows, so a search can
filter by meeting in the same query and an extracted row can point at the
turn it came from with a foreign key. Six tables: meetings, turns, chunks
(text, context header, embedding), decisions, action_items and traces. That
turn column is what makes a citation checkable instead of decorative.

The two paths through it, ingest and answer, are walked step by step under
[How it works](#how-it-works).

## 3. Production, scale and a hyperscaler

The demo is three processes on one laptop and one API key in a file. What
separates it from production is mostly the work around the model calls. In
the order I would do it:

**Packaging and deploy.** Dockerfiles for the API and the web app, next to
the Compose file that today runs only the database. Both services are
stateless, so they scale out behind a load balancer. Two things have to move
first. The migration runner now runs inside every API process at startup and
would race between replicas, so it becomes a release step. The embedding
model is downloaded on first use and loaded in-process, so a fresh replica
takes minutes to answer its first upload; bake the model into the image, or
move embeddings to a hosted endpoint (below). The answer stream is
server-sent events, so the load balancer needs response buffering off and an
idle timeout above the slowest answer; the API already sends the header that
tells a proxy not to buffer.

**Ingest as a job.** An upload runs two model passes and an embedding pass
inside the HTTP request. That is fine for a four-minute transcript and wrong
for a two-hour one. Put the file in object storage, enqueue a job, let a
worker run the same ingest function and mark the meeting ready, and have the
page poll. The worker is also where one global concurrency limit lives, so a
hundred uploads at once do not trip the model API's rate limit, and where a
backfill of an archive goes through the Batch API at half price.

**Tenants and access.** Log-in through the cloud's identity service, a
`tenant_id` on every table, and row-level security in Postgres so a query
cannot forget the filter. Vector search already filters by meeting and would
filter by tenant the same way; when a tenant's chunks outgrow one HNSW index,
partition the table. The agentic table of contents is the part that does not
scale as it stands: it lists every meeting and every extracted row, which
fits in one prompt for a team's quarter and not for a company's year. Scope
it per tenant and per time window, and past that build the query router the
design doc chose not to build at five meetings.

**Reliability and cost.** The SDK retries rate limits and server errors
twice. Above that there is nothing: a failed header call fails the whole
upload and stores nothing, so the job needs its own retry, an idempotency key
so a retried job does not store a meeting twice, a timeout per model call,
and a circuit breaker so an outage of the model API degrades to "try later"
rather than a queue of hung requests. Cost is already measured: every trace
records what its question cost, so a cap per user and per day is one query
and one check, with a billing alarm on the cloud side behind it. Prompt
caching is what keeps the agentic bill close to the classic one; the table
of contents must stay byte-stable per tenant so the cache keeps hitting.

**Secrets, data, privacy.** The key moves from `.env` to the cloud's secret
store. The database gets private networking, encryption at rest, backups and
a retention policy for traces, which store every question and answer in
full. Transcripts are the sensitive asset. The guardrail that treats them as
data rather than instructions stays, and the injection question in the
golden set becomes a regression test in CI.

**Observability.** Keep the traces ledger, which is the product's own account
of how it answered, and add the standard layer under it: structured logs,
OpenTelemetry traces per request with each model call as a span, dashboards
for latency, cost and refusal rate, and alerts on them. The eval runs nightly
against a fixed corpus and alerts when faithfulness moves more than the
twelve points the judge's own drift accounts for. The golden set against the
fakes runs on every pull request, offline, in seconds.

**Embeddings and models.** Embeddings move to a hosted endpoint: the
interface is two methods, the change is one migration for the vector width,
and the API image then carries no model. Claude is available on Bedrock,
Vertex AI and Microsoft Foundry, so on AWS, GCP or Azure the model calls can
stay inside the cloud's identity and billing instead of going out on a
third-party key.

Where each piece would land:

| | AWS | GCP | Azure | Cloudflare |
| --- | --- | --- | --- | --- |
| API and web | ECS on Fargate, or App Runner | Cloud Run | Container Apps | Workers for the Next.js app through OpenNext; the Python API in Containers |
| Postgres with pgvector | RDS or Aurora PostgreSQL | Cloud SQL for PostgreSQL | Database for PostgreSQL Flexible Server | None hosted: Postgres elsewhere behind Hyperdrive, or a rewrite of the store on D1 and Vectorize |
| Uploads and jobs | S3, SQS | Cloud Storage, Pub/Sub | Blob Storage, Service Bus | R2, Queues |
| Secrets | Secrets Manager | Secret Manager | Key Vault | Workers secrets |
| Log-in | Cognito | Identity Platform | Entra ID | Access |
| Claude | Bedrock | Vertex AI | Foundry | Anthropic API, through AI Gateway |
| Embeddings | Bedrock embedding models | Vertex AI embeddings | Azure OpenAI embeddings | Workers AI, which hosts bge-small-en-v1.5 itself |

Cloudflare is the natural home for the web tier and the least natural for
the API, which needs a Python runtime with ONNX and a Postgres driver; its
Containers product is what makes that fit.

## 4. RAG and LLM approach and decisions

Transcripts break chunk-and-embed in four ways, and the design follows from
them. The unit of meaning is a speaker turn, not a token count, so cutting
mid-turn loses who said what. Turns are not self-contained: "yeah, let's do
that by Friday" embeds to nothing useful, and half of any transcript looks
like that. The questions people ask are aggregations ("what did we decide?",
"what are my open items?"), which top-k similarity cannot answer however good
the reranker. And speaker and time are filters, not prose. So the index has
two layers, chunks of whole turns with a generated context header for search
and extracted decisions and action items anchored to turns for the
aggregations, and there are two ways to answer, both measured by the same
eval.

**LLM.** Considered: one model for everything, or a cheaper one where no
judgment is needed. Final: Opus 5 answers, extracts and drives the agent,
because the hard part of this task is judgment about what counts as a
decision and who owns a task, and at five meetings the cost is cents. Haiku
4.5 writes the context headers, one short sentence each, where a large model
adds nothing. Sonnet 5 judges the eval, never the model under test; I tried
Haiku first, and it scored the same reference answer 80%, 100% and 40%
across three runs. Thinking effort is a setting, high by default, and every
trace records latency, so that trade can be measured instead of guessed.

**Embedding model.** Considered: a hosted model (Voyage, OpenAI) or a local
one. Anthropic has no embeddings endpoint, so a hosted model means a second
vendor and a second key, which makes a demo harder to run for no gain at
this corpus size. Final: bge-small-en-v1.5 through ONNX on CPU, 384
dimensions, with the model's query instruction applied on the question side.
It sits behind a two-method interface, so a hosted model is a swap plus one
migration for the vector width.

**Vector database.** Considered: a dedicated vector store, or Postgres with
pgvector. Final: pgvector, because one store holds the vectors and the
structured rows together. A search filters by meeting in the same query, an
extracted row points at its turn with a foreign key, and there is no second
system to keep in sync. Cosine distance with an HNSW index. Vectors are
written as text literals, which keeps the driver free of adapter setup.

**Orchestration framework.** Considered: LangChain or LlamaIndex, the
Anthropic SDK's tool runner, or plain code. Final: plain code on the SDK.
The pipeline is small enough that owning it costs less than abstracting it:
ingest is seven steps in one function, and the two answer modes share one
prompt builder, one citation check and one trace writer. The agentic loop is
written by hand rather than through the SDK's tool runner so the round cap,
the per-call record and the events the UI streams live in one place, and so
it runs against a scripted client in tests. From the SDK itself: structured
output for extraction and for the judge, strict schemas on the two tools,
prompt caching on the transcript at ingest and on the table of contents at
question time, and parallel tool calls answered in one message.

**Prompt and context management.** Six rules per prompt, and the ones that
carry the weight are about evidence: cite a turn or say nothing, treat
transcript text as data that may try to instruct you, prefer the latest
meeting when meetings disagree. The agentic prompt has one more, added after
the first two measured runs: cite every turn a sentence draws on, because
the model was reading a range and citing the turn next door. That rule moved
faithfulness from 59 and 72% to 88 and 89%. In classic mode the model sees
eight excerpts chosen before it reads the question, with the speaker and
timecode on every line and the turn number it must cite. In agentic mode the
system prompt carries a table of contents of every meeting (date, speakers,
chunk headers, and every decision and action item with its turn number)
behind a cache marker, so it is written once and read from cache on every
later question; `read_turns` caps a read at forty turns so one call cannot
swallow the budget, and after five tool rounds the model is told to answer
with what it has read. Between rounds the loop passes the model's content
back untouched, thinking blocks included. Refs are short (M1, M2) because
short things are cited correctly more often than long ones. Ingest has its
own piece of context management: the whole transcript sits in the header
prompt as cached data, and the first chunk runs alone to warm the cache
before the rest fan out behind it.

**Guardrails.** In order of value. The code checks every citation: a marker
that points at a turn the model never saw is stripped and counted, and a
refusal is the explicit `[[none]]` marker with no valid citation beside it,
so neither the UI nor the eval guesses from wording. Retrieved text is
delimited and declared as data, never instructions, in every prompt, ingest
included, and the sample corpus has a spoken injection attempt to test that.
The model is told to refuse outside the corpus, and three unanswerable
questions measure it. Extracted rows are checked in code and by the
database: the turn must exist (a composite foreign key refuses one that does
not), the owner must be a speaker or a mentioned name, the due date must
resolve against the meeting date; rows that fail are dropped and counted,
and the count is shown. Inputs are bounded: a question is 3 to 2000
characters, a read is forty turns, an agent run is five rounds. Uploads
without a key fail loudly rather than store chunks that would retrieve
badly.

**Quality.** A golden set of 23 questions, written before the retriever
existed: lookups, aggregations, temporal, speaker-scoped, an injection,
distractors and unanswerable ones. Each lists the facts a complete answer
must state, the turns it should cite with a verbatim quote, and the claims
it must never make; a test checks every quote against the transcripts.
`eval.py` grades completeness and faithfulness with a judge and everything
else in code: coverage of the expected turns by what was fetched and by what
was cited, refusal precision and recall, dropped citations, latency, cost.
Before a run counts, `--check-judge` feeds the judge a reference answer, an
"I don't know" and an answer built from the forbidden claims, and fails if
the verdicts are wrong. `--regrade` re-judges a saved run for cents, which is
how I measured the judge's own drift: one to four flipped verdicts out of
seventeen or eighteen, so a gap under about twelve points between two runs
is noise. Every run is committed under `eval-runs/` with an index, and the
results are under [What the numbers say](#what-the-numbers-say). The
deterministic parts (parser, chunker, citation check, grading arithmetic)
have unit tests, and the recording behind test mode has a test that fails
when the transcripts, the chunker or the golden set change under it.

**Observability.** Every question writes a trace: mode, what was retrieved or
which tools ran with what arguments, tokens in and out with cache reads and
writes apart, latency, cost computed from the token counts the API reports
and the model that served the request, the answer and its citations. The
traces page is a ledger, and a trace opens in the same answer view the Ask
page uses, so what a reviewer verifies later is exactly what the asker saw.
While an answer is on its way, the page shows each tool call as it happens.
I built this myself instead of wiring in a vendor dashboard because the
point is to show the reasoning: which turns the model read, in what order,
what each call cost. A hosted tracer would be the next layer under it, not a
replacement.

## 5. Key technical decisions and why

**Two layers, no router.** Chunks with embeddings answer lookups; the
decisions and action items extracted at ingest answer the aggregation
questions people ask most. At five meetings the extracted layer fits in a
prompt whole, so a router would only add a way to be wrong. The threshold
where one becomes necessary is written down, not built.

**Two answer modes, and a measurement instead of a choice.** Classic is the
degenerate case of agentic, so both together cost about an hour more and
bought a comparison on numbers. Classic wins on latency and matches agentic
on lookups; agentic fixes the one aggregation question classic kept missing,
because the table of contents shows it which meetings to read. The idea for
agentic mode came from Anthropic's guidance on progressive disclosure: show
the model an index, let it fetch details.

**Chunking.** Fixed-size chunks cut turns in half and lose who said what, so
chunks are windows of whole turns. Overlap is one turn, because the failure
that matters is a question in one chunk and its answer in the next. The
500-token size is a guess I didn't get to test. The eval showed that at this
size, whether a single line can be found at all can hinge on one generated
header sentence, so smaller chunks are the first thing I'd try.

**Context headers at ingest.** One sentence per chunk from Haiku that places
it inside the meeting, embedded together with the chunk. This is what makes
"yeah, by Friday" retrievable, and it is also part of the noise floor:
re-ingesting the same files regenerates the headers, which once moved a
chunk out of the top eight and turned a correct answer into a refusal.

**Extraction anchored to turns.** Every decision and action item must name
the turn it was said in or be left out, and a task someone mentions is not a
task they own. The database refuses a row that points at a turn that does
not exist, and code checks the rest. That column is what turns a citation
into something a reader can click and verify.

**The index stays out of classic mode.** Putting the extracted rows into the
classic prompt fixed the same aggregation question but cut faithfulness by a
quarter at 40% more cost: a row summarises several turns but anchors to one,
so the model cited the anchor and said more than that turn contains. Prompt
rules did not fix it. Agentic mode gets the same rows as navigation only and
has to read a turn before it may cite it, which is the structural fix.

**Inline citation markers over a structured claims list.** The model writes
`[[M2#5]]` right after a claim; code resolves it to meeting, turn, speaker,
timecode and text. Each citation sits next to the sentence it supports, the
text streams as is, and validation stays in code.

**Next.js plus FastAPI.** Two services cost about two hours of plumbing in a
fifteen-hour budget, but the split mirrors how AI teams run and each side
uses the language it is best at. The browser never talks to the API: route
handlers forward writes and the stream, server components read, and there
is no CORS.

**Plain SQL, no ORM.** Six tables and one interesting query (vector
similarity with a filter) do not need an ORM, and an ORM would hide that
query. psycopg with numbered migration files, applied at startup.

**Test mode is a recorded replay, not a mock.** A reviewer without a key used
to see an empty app. The recording holds real Opus answers with real
citations, captured for nothing from eval runs already made, and everything
after the model's words runs for real: retrieval, the tool calls through the
real executor, the citation check, the trace. Every recorded answer is
marked, because a replayed answer must never pass for a live one.

**Streaming what earns it.** Both modes answer through one event stream;
agentic sends a `tool_call` event per call as it happens, classic sends the
one `answer` event, so the page has one code path. The answer text itself is
not streamed yet.

**UI.** One accent, reserved for the cited moment. The chip in the answer,
the quoted moment under it and the turn in the transcript all light up the
same way, so the three pages read as one system. Citations are chips in the
text plus a list under the answer, not tooltips or a side panel, because the
quoted turn needs room to be read, tooltips do not work on touch, and a list
can be walked with the keyboard.

**One golden label changed after I saw results.** The CFO's name is
unknowable from the transcripts, but a cited "never named, mentioned here
and here" beats a bare refusal, so that question became a distractor and a
truly unanswerable one took its place. Changing a key after seeing results
is dangerous; it is disclosed here and in the design doc for that reason.

## 6. Engineering standards

What I held to:

- Test-first, and a suite that runs offline. Every model-backed service
  (header writer, extractor, answerer, agent, embedder) sits behind a small
  interface with a fake, injected through FastAPI's dependency overrides.
  265 API tests and 76 web tests run in a few seconds each, with no key.
  Three of them load the real embedding model, downloaded once; the rest
  run against the fakes.
- Storage and API tests against the real database. They use the Postgres
  from Compose in a sibling `meetings_test` database, recreated from an
  empty schema for every test, so development data is never touched. Without
  `DATABASE_URL` they are skipped, not faked.
- Typed boundaries. Pydantic models on every request, response and stored
  row; schema-validated structured output for extraction and for the judge;
  strict schemas on the agent's tools; TypeScript in strict mode with
  ESLint's Next.js and TypeScript rules.
- The database enforces what it can: composite foreign keys from extracted
  rows to turns, a check constraint on chunk ranges, cascading deletes, one
  transaction per ingest, and numbered migrations applied in one transaction
  and recorded.
- Model output is never trusted as is. Citations, extracted rows and tool
  arguments are validated in code, and a policy refusal is a 502 with a
  message rather than an empty answer.
- Errors fail loudly and early: 422 for a file with no turns or not in
  UTF-8, 503 without a key, 409 when test mode has no corpus, and an `error`
  event on the stream instead of a hung connection.
- Measurements are reproducible: eval runs committed with an index, regrades
  kept next to their originals, the judge probed with known answers before
  its verdicts count, variants compared across at least two runs, and a test
  that fails when the recording drifts from the fixtures.
- Configuration through the environment with a checked-in example. The key
  never enters git and never passed through the assistant.
- Cost from the token counts the API reports and the model that served the
  request, never from string-length estimates; an unknown model costs zero
  rather than a made-up number.
- A design doc with a dated decisions log, written as the decisions were
  made, and commit subjects in the conventional form.

What I skipped:

- No CI. Both suites and the lint run on my laptop, and nothing runs on
  push. A workflow with both suites, the lint and the golden set against the
  fakes is the first item on the production list.
- No linter, formatter or type checker for Python. The code is annotated
  throughout, but nothing checks the annotations.
- No Dockerfiles for the two services; only the database runs in Compose.
- No pre-commit hook and no root `.gitignore`, which is how three
  `.DS_Store` files got into the tree.
- No log-in, no tenants, no rate limiting. The API listens on localhost and
  trusts whoever reaches it.
- Retries stop at the SDK's default two. A failed header call fails the
  upload, and nothing is stored.
- One branch, no pull requests, and the only reviewer was me.
- Chunk sizes come from an estimate of four characters per token. It is
  documented, and a 20% error does not change retrieval.
- The web tests drive components and route handlers under jsdom; nothing
  drives a real browser end to end.

## 7. How I used AI tools

I built this with Claude Code, and it did most of the typing. My part was the
direction: the stack and the timebox, the sign-off on the two-layer design,
the decision to build both answer modes and compare them, the brief for the
sample meetings and the sign-off on the golden questions, and the review of
every slice before I committed it. The agentic mode came from a page in
Anthropic's docs on progressive disclosure that I brought into the session.
The assistant wrote the code test-first, a failing test and then the code
that passes it, ran the evals, and drafted this README and the design doc,
which I reviewed. The launch configuration under `.claude/` is the one it
used to start both services and look at the pages in a browser while it
worked. The golden set records its own provenance in the file: questions,
answers and key facts drafted with the assistant from the transcripts, then
reviewed by hand, with every expected turn checked against the transcripts
by a test.

Two rules held throughout: the API key never passed through the assistant,
and nothing was committed that I hadn't reviewed. The eval exists partly
because of this setup. When a tool writes most of the code, a judge that
scores the output is a better way to know whether a change helped than
reading diffs.

## What you get

Three pages and one API.

**Meetings.** Upload a `.txt` transcript with one line per turn, such as
`[00:12:04] Marco: Arrancamos.` The meeting page shows the transcript as a
timeline. Every timecode is a link to its turn, and a linked turn gets a
highlighter stroke. The decisions and action items extracted at upload come
back with the meeting from the API; a panel for them on this page is on the
list below.

**Ask.** A question box with a Classic and an Agentic mode. While the answer
is on its way, the page shows what the model reads, one line per tool call as
it happens. In the answer, each citation is a chip with the meeting ref and
the timecode. Under the answer, the cited moments are quoted in full, with
the speaker and a link into the transcript; pressing a chip marks its moment
with the same highlighter the transcript uses. A fold shows how the answer
was made: tool calls or retrieved excerpts, tokens, cache hits and cost.
Answers stack under the box, newest first. The newest is open and the earlier
ones fold under their question; press a question to open or fold its answer.

**Test mode.** A switch under the question box, with a line that says why it
is there. On, it lists the sample questions grouped by what each one tests,
and a press on one asks it. The answer is the one a real run of this app
gave, replayed: only the model's words are recorded, and retrieval, the tool
calls, the citation check and the trace run again for real. A recorded
answer wears a dashed border, says "test mode" next to its mode, and shows
as such in the traces ledger, so it can never pass for a live one. The
recording is `fixtures/test-mode.json`, written by `api/record.py` from a
database that holds a seeded corpus and an eval run of each mode;
`api/tests/test_recording.py` fails when the transcripts, the chunker or the
golden set change under it.

**Traces.** Every answered question with its mode, citations, latency and
cost, and a detail page with the same answer view plus the tool arguments
and the token breakdown.

**API.** `POST /meetings`, `POST /meetings/samples`, `GET /meetings`,
`GET /meetings/{id}`, `POST /ask`, `POST /ask/stream`, `GET /traces`,
`GET /traces/{id}`, `GET /test-mode` and `GET /health`. FastAPI serves the
interactive docs at `/docs`.

The sample corpus is five short meetings of a fictional product team over
September 2026: a quarterly planning, two weekly syncs, a design review and a
retro. They were written so that the interesting questions have answers
spread across meetings, dates that move, tasks that change owner, one
distractor, and one line where a speaker tries to instruct the AI.

## How it works

**Ingest** (`POST /meetings`) runs seven steps.

1. Parse the file into turns. No model; a line with a timestamp starts a
   turn, a line without one continues the turn above. A file with no turn at
   all is rejected with a 422.
2. Chunk into windows of whole turns, about 500 tokens each, with one turn of
   overlap so a question and its answer land together at least once. The
   speaker and timecode stay on every line.
3. Write a context header per chunk with Claude Haiku 4.5: one sentence that
   places the chunk inside the meeting. The transcript sits in the prompt as
   cached data. This is what makes "yeah, by Friday" retrievable.
4. Embed header plus chunk locally with bge-small (384 dimensions) and store
   the vector in pgvector.
5. Extract decisions and action items from the whole transcript with Claude
   Opus 5 and structured output. Each row must name the turn it comes from,
   and a task someone mentions isn't a task they own.
6. Check the rows in code. The turn must exist, the owner must be a speaker or
   a mentioned name, the due date must resolve against the meeting date. Rows
   that fail are dropped and counted.
7. Store meeting, turns, chunks and rows in one transaction.

**Answering** (`POST /ask` with `mode`) shares one index builder, two
retrieval functions, one answer format, one citation check and one trace
writer between the modes. The difference is who decides what the model reads.

- Classic: the system decides. Embed the question, take the eight closest
  chunks, one call to Opus, check the citations. About seven seconds.
- Agentic: the model decides. The system prompt carries a table of contents
  of every meeting (date, speakers, chunk headers, and every extracted
  decision and action item with its turn number), cached between questions.
  The model gets two tools, `search_transcripts` and `read_turns`, and up to
  five rounds. Only turns fetched through a tool can be cited; the table of
  contents shows where to look and can't be cited itself. Parallel tool
  calls are answered in one message, tool errors go back to the model as
  error results, and each call streams to the page as it happens.

**Citations.** The model writes `[[M2#5]]` right after a claim: meeting ref
and turn number, as shown to it. Code resolves each marker to meeting, turn,
speaker, timecode and text, strips any marker that points at a turn the model
never saw, and counts those as dropped. A refusal is the marker `[[none]]`
with no valid citation beside it.

**Traces.** Every question writes a row: mode, what was retrieved or which
tools ran with what arguments, tokens in and out with cache reads and writes
apart, latency, cost, the answer and its citations.

The full reasoning, with a dated decisions log, is in
[docs/design.md](docs/design.md).

## What the numbers say

Same corpus, 23 questions, two runs per column, one judge (Sonnet 5) for all
six runs. Faithfulness is judged on answered questions only.

| | Classic | Agentic, first prompt | Agentic, citing rule |
| --- | --- | --- | --- |
| Completeness | 94 / 94% | 94 / 96% | 90 / 93% |
| Faithfulness | 89 / 82% | 59 / 72% | 88 / 89% |
| Expected turns cited | 93 / 93% | 90 / 91% | 90 / 90% |
| "What did Diego commit to?" | 0.78 | 0.89 / 1.00 | 1.00 / 1.00 |
| Mean latency | 7.5 / 7.1 s | 10.9 / 11.0 s | 10.8 / 11.2 s |
| Cost per run | $1.06 / 1.05 | $1.21 / 1.09 | $1.21 / 1.10 |

What I take from it:

- Classic wins on latency and is as complete as agentic on lookups. Agentic
  fixes the one aggregation question classic kept missing, because the table
  of contents shows it which meetings to read. Cost is close, because the
  table of contents is served from cache.
- Agentic's completeness dip sits on one question in both runs: a task that
  the table of contents listed with the owner it got later, so the model had
  no cue that it started unowned. Two runs can't say whether the new rule
  caused that.
- Putting the extracted index into the classic prompt fixed the same
  aggregation question but cut faithfulness by a quarter at 40% more cost, so
  I left it out of classic. Agentic gets the same rows as navigation and has to
  read before it cites, which is the structural fix.
- The judge has its own drift: re-judging identical answers flipped one to
  four faithfulness verdicts out of seventeen or eighteen. A gap under about
  twelve points between two runs is noise. It also reads a supported negative
  answer ("no raise was approved, the only mention was a joke") as a refusal,
  which costs refusal precision one or two false positives per run.
- Re-ingesting the same files regenerates the context headers and moved one
  chunk out of the top eight, which turned a correct answer into a refusal.
  Ingest is part of the noise floor.

The runs are in [eval-runs/](eval-runs/INDEX.md), one directory per run with
a graded row per question.

## Tests and evaluation

```bash
cd api && uv run pytest
```

```bash
cd web && npm test
```

Storage and API tests need the database from Compose and use a sibling
`meetings_test` database, recreated per test. Without `DATABASE_URL` they are
skipped.

```bash
cd api && uv run python eval.py --check-judge
```

```bash
cd api && uv run python eval.py --mode classic
```

```bash
cd api && uv run python eval.py --mode agentic
```

A run costs about $1.30 with the judge. Numbers move a few points between
runs, so I compare variants across at least two runs each.

## What I would do next

- A panel of decisions and action items on the meeting page, each row a
  link to its turn, and a status that can be edited.
- The chunk-size experiment, measured with two ingests per size, and a look
  at the unowned-task question with a third run before any prompt change.
- Hybrid retrieval: a keyword index next to the vectors, because names and
  product terms are exact-match queries in disguise.
- Stream the answer text itself, not only the tool calls.
- A Whisper adapter behind the parser interface for the voice bonus.
- The production list under [question 3](#3-production-scale-and-a-hyperscaler),
  in that order.

## Layout

```
api/            FastAPI service: app/ (ingest, retrieval, answering, agent), evaluation/, tests/; record.py writes test mode's recording
web/            Next.js app: meetings, ask and traces pages
fixtures/       five sample transcripts, the golden question set and the recorded run test mode replays
eval-runs/      one directory per evaluation run, with an index
docs/design.md  the design and its decisions log
scripts/        seed.sh uploads the fixtures
```

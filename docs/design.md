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

The Ask page is that stream made visible. A question box with a mode switch
sits on top; answers stack under it, newest first. While an answer is on its
way the page shows what the model is doing, one line per tool call as the
event arrives (which turns it read, what it searched, how long the call
took), so the wait reads as work. In the answer, every marker the model wrote
becomes a small chip where it stood (meeting ref and timecode), and under
the answer a list of cited moments quotes each turn in full, with the speaker
and a link into the transcript. Pressing a chip marks its moment with the
same highlighter stroke the transcript uses for a linked turn, so the two
pages read as one system. A "How it was answered" fold shows the tool calls
or the retrieved excerpts, tokens, cache hits and cost. Answers persist for
the browser session, so a trip into a transcript and back loses nothing.

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
the two retrieval functions, the answer format, the citation check and the
trace writer. The difference is who decides what the model reads.

The answer is plain text with inline markers: the model writes `[[M2#5]]`
right after a claim, naming the excerpt's short ref and the turn number it
was shown. Code resolves each marker to meeting, turn, speaker and timecode,
strips any marker that points at a turn the model never saw, and counts
those as dropped citations. A refusal is the explicit marker `[[none]]` with
no valid citation beside it, so the eval counts refusals without guessing
from wording, and an answer that cites real turns is never a refusal. Plain text with
markers also streams naturally, which matters for agentic mode.

In classic mode the system decides. Embed the question, take the top 8 chunks,
make one model call, check the citations, answer. One call, predictable,
about seven seconds with Opus. Its weakness is that the evidence is chosen
before the model knows what it needs. If the answer lives in two meetings and
the top 8 came from one, there is no way to ask for more.

The plan was to also append every extracted row as an index. Measured on
identical retrieval (two runs each way), that fixed the one aggregation
question it was built for (Diego's commitments, 0.78 to 1.00) and left
overall completeness unchanged, but cut faithfulness from about 90% to about
65% at 40% more cost. The cause is structural: an extracted row summarises
several turns but anchors to one, so the model cites the anchor and says more
than that turn contains. Prompt rules did not fix it. Classic mode therefore
runs without the index by default (`use_index` on the request turns it on);
the extraction stays for the meeting page and for agentic mode, where the
model reads a row's neighbourhood before citing. The proper fix, a turn range
per row, is listed under next steps.

In agentic mode the model decides. The system prompt carries a table of
contents (each meeting with title, date, speakers, its chunk headers as an
outline, and every decision and action item with its turn number), cached
between questions. The model gets two tools, `search_transcripts(query,
meeting?)` and `read_turns(meeting, start, end)`, and a hand-written loop
allows at most five tool rounds before forcing an answer. Only turns fetched
through a tool are citable; the table of contents is navigation, not evidence.
That is the structural answer to what sank the index in classic mode: an
extracted row anchors to one turn but summarises several, so the model must
read the neighbourhood before it may cite. Its costs are latency, tokens and
the extra ways a loop can fail; tool errors go back to the model as error
results, parallel calls are answered in one message, and tool calls stream to
the UI so the wait reads as work. The loop is hand-written rather than the
SDK's tool runner so the round cap, the per-call record and the streamed
events live in one place and run against a scripted client in tests.

Measured on the same seed as classic, two runs per variant and one judge
for all of them, agentic mode matched classic on completeness (94 to 96%
against 94%) and on coverage, fixed the aggregation question classic kept
missing (Diego's commitments, 1.00 on both runs with the current prompt
against 0.78), cost 5 to 15% more in dollars because the table of contents is
served from the prompt cache, and took about half again as long (11 s against
7.3 s). Its first prompt cited sparsely: the model read a range and cited the
neighbouring turn, which the faithfulness check flags (59 and 72% against 82
and 89% for classic). A rule to cite every turn a sentence draws on, with the
date and the reason named as the usual stragglers, took faithfulness to 88 and
89% on two runs, above the judge's own drift (see Evaluation). Completeness
moved to 90 and 93%, and the gap sits on one question in both runs, the tasks
raised without an owner. In one run the agent read the retro turns where the
task came up and still left it out; in the other it never opened the retro.
The table of contents already showed that task with the owner it got later,
so the agent had no cue that it started unowned. That is a reasoning miss,
and two runs cannot say whether the rule caused it. A refusal in this mode
usually cites the turns that show what the meetings do cover, so the API's
`[[none]]` marker fired on one answer in two runs; the eval reads refusals
through the judge for that reason.

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

A golden set of 23 questions in `fixtures/golden.json`, written before the
retriever. Each answerable question lists the turns that support it, with a
verbatim quote that a test checks against the transcripts, plus the atomic
facts a complete answer states and the propositions a correct answer must
never assert. Types: lookup, aggregation, temporal, speaker-scoped, an
injection attempt spoken inside a meeting, a distractor, and unanswerable
questions that must be refused. `eval.py` prints, per mode: key-fact
completeness and faithfulness against cited turns (an LLM judge), coverage of
the golden turns by what was fetched and by what was cited, refusal precision
and recall, latency and cost per question.

The judge is Sonnet 5, never the model under test. Haiku was tried first and
scored the same reference answer 80%, 100% and 40% across three runs; Sonnet
gave identical verdicts on two runs of the known-answer probes. Before any
run counts, `eval.py --check-judge` feeds the judge the reference answer, "I
don't know", and an answer built from the forbidden claims, and fails if the
verdicts are not what a working judge must produce. Faithfulness applies to
answered questions only: a refusal makes no cited claim, and a refusal that
invents things is caught by the forbidden-claim check instead. Whether an
answer is a refusal is the judge's call (`declines`), because a good refusal
often cites the turns that show what the meetings do cover; the API's
`[[none]]` marker stays as the deterministic flag the UI uses. A saved run
can be re-judged without asking the API again (`eval.py --regrade`), so a
judge change costs cents rather than dollars.

Re-judging the same answers is also how the judge's own drift was measured.
Across four regrades it flipped one to four faithfulness verdicts out of
seventeen or eighteen answered questions, two net at most, so a faithfulness
gap under about twelve points between two runs is noise. The judge also reads
a supported negative answer ("no raise was approved; the only mention is a
joke") as a refusal, which shows up as one or two false positives in refusal
precision on every run, on the injection question and sometimes on the
Android distractor; both answers score complete.

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
- 2026-09-07. Extraction runs concurrently with the context-header calls at
  ingest, since neither needs the other. Extracted rows carry a composite
  foreign key onto the turn they cite, so the database refuses a row that
  points at a turn that does not exist; the code check on top of it
  normalises names, dates and status and counts what it drops. At question
  time the index turns are citable like retrieved turns, through the same
  validator, so a citation into the index is checked the same way.
- 2026-09-07. Two findings from the index experiment. First, on identical
  retrieval the index fixed one aggregation question and cut faithfulness
  by a quarter at 40% more cost, so classic mode runs without it by default.
  Second, re-ingesting the same transcripts regenerates the context headers,
  which moved one chunk out of the top eight and turned a correct answer
  into a refusal: at 500-token chunks a single line's reachability hinges on
  one generated sentence. Ingest variance is part of the noise floor, and
  smaller chunks are the first thing to try next, measured the same way.
- 2026-09-07. After the first eval run, one golden label changed: the CFO's
  name is unknowable, but a cited "never named, mentioned here and here" beats
  a bare refusal, so that question became a distractor and a truly
  unanswerable one (cloud provider) took its place. Changing a key after
  seeing results is dangerous; this one is disclosed for that reason.
- 2026-09-07. Inline citation markers over a structured claims list: each
  citation sits next to the sentence it supports, the text streams as is,
  and validation stays in code. Classic mode ships without streaming; the
  one call it makes returns everything the eval and the traces page need.
  Streaming arrives with agentic mode, where progress events earn it.
- 2026-09-07. Local embeddings (bge-small via fastembed) over Voyage or OpenAI:
  one credential to run the whole demo, quality that is enough for five
  meetings, and a documented swap path. Model-backed services are injected as
  dependencies so the test suite runs offline against fakes; the embedder loads
  on first use so tests never pull the model.
- 2026-09-07. The agentic prompt tells the model to cite every turn a
  sentence draws on, with the date and the reason named as the usual
  stragglers. Two runs against two regraded runs of the earlier prompt:
  faithfulness 88 and 89% against 59 and 72%, completeness 90 and 93% against
  94 and 96%, with the completeness gap on one question. The rule stays, and
  that question is the next thing to look at, with a third run before any
  prompt change. The earlier runs were re-judged with the current judge so
  that no number compares across judge versions; the regraded copies sit
  next to the originals in `eval-runs/`.
- 2026-09-07. Citations in the answer are chips, and the evidence is a list
  under the answer rather than a tooltip or a side panel: the quoted turn
  needs room to be read, tooltips do not work on touch, and a list can be
  keyboard-walked. The chip carries the meeting ref and the timecode, the
  list carries the words. Both modes answer through `/ask/stream`; classic
  sends a single answer event, so the page has one code path. The link from
  a cited moment into the transcript is a plain anchor, because the
  transcript highlights the linked turn with CSS `:target`, which browsers
  re-evaluate only on a real fragment navigation and not on the pushState a
  client-side link performs.

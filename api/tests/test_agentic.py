"""The agent loop against a scripted client, and the table of contents it starts from."""

from datetime import date
from uuid import uuid4

import pytest

from app.agentic import AGENT_MODEL, TOOLS, ClaudeAgent, ToolError, render_index
from app.models import IndexRow, MeetingOutline

pytestmark = pytest.mark.anyio

MEETING_A, MEETING_B = uuid4(), uuid4()
REFS = {MEETING_A: "M1", MEETING_B: "M2"}
OUTLINES = [
    MeetingOutline(meeting_id=MEETING_A, title="q4-planning", meeting_date=date(2026, 9, 1), turn_count=33,
                   speakers=["Ana", "Marco"], headers=["Planning pricing.", "Deciding on mobile."]),
    MeetingOutline(meeting_id=MEETING_B, title="retro", meeting_date=None, turn_count=30, speakers=["Diego"], headers=[]),
]
ROWS = [
    IndexRow(kind="decision", meeting_id=MEETING_A, meeting_title="q4-planning", meeting_date=date(2026, 9, 1),
             turn=25, text="No mobile app in Q4.", who="Marco", due_text=None, due_date=None, status=None),
    IndexRow(kind="action", meeting_id=MEETING_B, meeting_title="retro", meeting_date=None,
             turn=28, text="Write the deploy process.", who="Diego", due_text="mid October", due_date=date(2026, 10, 15), status="open"),
]


def test_index_shows_each_meeting_with_ref_outline_and_rows_but_no_citation_markers():
    text = render_index(OUTLINES, ROWS, REFS)

    assert '<meeting ref="M1" title="q4-planning" date="2026-09-01" turns="0-32" speakers="Ana, Marco">' in text
    assert "outline: Planning pricing." in text
    assert "turn 25, decision (Marco): No mobile app in Q4." in text
    assert "turn 28, action (owner: Diego, due: mid October (2026-10-15), open): Write the deploy process." in text
    assert 'date="unknown"' in text
    assert "[[" not in text, "index rows must not look citable"


def test_tools_are_strict_with_every_field_required():
    for tool in TOOLS:
        schema = tool["input_schema"]
        assert tool["strict"] is True
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])
    assert [t["name"] for t in TOOLS] == ["search_transcripts", "read_turns"]


# ---- a scripted Anthropic client ----
class _Text:
    type = "text"

    def __init__(self, text):
        self.text = text


class _Thinking:
    type = "thinking"
    thinking = "(hidden)"


class _ToolUse:
    type = "tool_use"

    def __init__(self, id, name, input):
        self.id, self.name, self.input = id, name, input


class _Usage:
    input_tokens = 100
    output_tokens = 20
    cache_read_input_tokens = 5
    cache_creation_input_tokens = 0


class _Response:
    def __init__(self, content, stop_reason):
        self.content, self.stop_reason = content, stop_reason
        self.usage = _Usage()
        self.model = AGENT_MODEL


class ScriptedClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.messages = self

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class UntilForbiddenClient:
    """Keeps calling tools until tool_choice forbids them."""

    def __init__(self):
        self.calls = []
        self.messages = self

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("tool_choice") == {"type": "none"}:
            return _Response([_Text("Best effort. [[M1#3]]")], "end_turn")
        return _Response([_ToolUse(f"t{len(self.calls)}", "read_turns", {"meeting_ref": "M1", "start": 0, "end": 5})], "tool_use")


async def _executor(name, input):
    return f"result of {name} {input}", f"{name} ok"


SYSTEM = [{"type": "text", "text": "rules"}]


async def test_loop_runs_tools_records_them_and_returns_the_final_text():
    client = ScriptedClient([
        _Response([_Thinking(), _ToolUse("t1", "search_transcripts", {"query": "pricing", "meeting_ref": None})], "tool_use"),
        _Response([_ToolUse("t2", "read_turns", {"meeting_ref": "M1", "start": 5, "end": 9})], "tool_use"),
        _Response([_Text("The date moved. [[M1#7]]")], "end_turn"),
    ])
    seen = []

    async def executor(name, input):
        seen.append((name, input))
        return f"turns for {name}", f"{name}: 1 excerpt"

    run = await ClaudeAgent(client).run(system=SYSTEM, question="When?", execute_tool=executor)

    assert run.text == "The date moved. [[M1#7]]"
    assert run.rounds == 2
    assert [c.name for c in run.tool_calls] == ["search_transcripts", "read_turns"]
    assert run.tool_calls[1].summary == "read_turns: 1 excerpt"
    assert seen == [("search_transcripts", {"query": "pricing", "meeting_ref": None}), ("read_turns", {"meeting_ref": "M1", "start": 5, "end": 9})]
    assert (run.input_tokens, run.output_tokens, run.cache_read_tokens) == (300, 60, 15)
    third = client.calls[2]
    assert third["model"] == AGENT_MODEL and third["tools"] is TOOLS and third["system"] is SYSTEM
    history = third["messages"]
    assert history[0] == {"role": "user", "content": "When?"}
    assert history[1]["role"] == "assistant" and history[1]["content"][0].type == "thinking", "thinking blocks go back untouched"
    assert history[2]["content"][0] == {"type": "tool_result", "tool_use_id": "t1", "content": "turns for search_transcripts"}
    assert history[4]["content"][0]["tool_use_id"] == "t2"


async def test_parallel_tool_uses_get_all_their_results_in_one_message():
    client = ScriptedClient([
        _Response([_ToolUse("a", "read_turns", {"meeting_ref": "M1", "start": 0, "end": 3}),
                   _ToolUse("b", "read_turns", {"meeting_ref": "M2", "start": 0, "end": 3})], "tool_use"),
        _Response([_Text("Done. [[M1#1]]")], "end_turn"),
    ])

    run = await ClaudeAgent(client).run(system=SYSTEM, question="q", execute_tool=_executor)

    assert run.rounds == 1 and len(run.tool_calls) == 2
    results = client.calls[1]["messages"][2]["content"]
    assert [r["tool_use_id"] for r in results] == ["a", "b"]


async def test_round_cap_forces_a_final_answer_without_tools():
    client = UntilForbiddenClient()

    run = await ClaudeAgent(client).run(system=SYSTEM, question="q", execute_tool=_executor, max_rounds=2)

    assert run.rounds == 2
    assert run.text == "Best effort. [[M1#3]]"
    final = client.calls[-1]
    assert final["tool_choice"] == {"type": "none"}
    assert "all tool rounds" in final["messages"][-1]["content"][-1]["text"]
    assert all("tool_choice" not in c for c in client.calls[:-1])


async def test_tool_errors_go_back_to_the_model_as_error_results_and_the_loop_continues():
    client = ScriptedClient([
        _Response([_ToolUse("t1", "read_turns", {"meeting_ref": "M9", "start": 0, "end": 3})], "tool_use"),
        _Response([_Text("Nothing there. [[none]]")], "end_turn"),
    ])

    async def failing(name, input):
        raise ToolError("unknown meeting ref M9")

    run = await ClaudeAgent(client).run(system=SYSTEM, question="q", execute_tool=failing)

    result = client.calls[1]["messages"][2]["content"][0]
    assert result["is_error"] is True and "M9" in result["content"]
    assert run.tool_calls[0].summary.startswith("error")
    assert run.text == "Nothing there. [[none]]"


async def test_a_policy_refusal_ends_the_run_with_that_stop_reason():
    client = ScriptedClient([_Response([], "refusal")])

    run = await ClaudeAgent(client).run(system=SYSTEM, question="q", execute_tool=_executor)

    assert run.stop_reason == "refusal" and run.text == ""


async def test_each_tool_call_is_reported_as_it_happens():
    client = ScriptedClient([
        _Response([_ToolUse("t1", "read_turns", {"meeting_ref": "M1", "start": 0, "end": 3})], "tool_use"),
        _Response([_Text("ok [[M1#1]]")], "end_turn"),
    ])
    events = []

    async def sink(call):
        events.append(call.name)

    await ClaudeAgent(client).run(system=SYSTEM, question="q", execute_tool=_executor, on_tool_call=sink)

    assert events == ["read_turns"]


def test_rules_ask_for_every_turn_a_sentence_draws_on():
    from app.agentic import SYSTEM_RULES

    assert "every turn a sentence draws on" in SYSTEM_RULES

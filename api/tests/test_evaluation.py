"""The eval's arithmetic, kept pure so it can be trusted without a model in the loop."""

from evaluation.grading import (
    ExpectedTurn,
    Row,
    refusal_metrics,
    summarize,
    turn_coverage,
)

RETRIEVED = [
    {"meeting_title": "2026-09-08-weekly-sync", "turn_start": 0, "turn_end": 16},
    {"meeting_title": "2026-09-01-q4-planning", "turn_start": 15, "turn_end": 32},
]
CITATIONS = [{"meeting_title": "2026-09-08-weekly-sync", "turn": 5}]


def test_coverage_counts_expected_turns_inside_retrieved_ranges_and_among_citations():
    expected = [
        ExpectedTurn(meeting="2026-09-08-weekly-sync", turn=5, quote="x"),   # retrieved and cited
        ExpectedTurn(meeting="2026-09-01-q4-planning", turn=20, quote="x"),  # retrieved only
        ExpectedTurn(meeting="2026-09-01-q4-planning", turn=3, quote="x"),   # neither
        ExpectedTurn(meeting="2026-09-29-retro", turn=1, quote="x"),         # other meeting
    ]

    retrieved, cited = turn_coverage(expected, RETRIEVED, CITATIONS)

    assert retrieved == 0.5
    assert cited == 0.25


def test_coverage_is_undefined_when_nothing_is_expected():
    assert turn_coverage([], RETRIEVED, CITATIONS) == (None, None)


def test_refusal_metrics_are_precision_and_recall_of_refusing():
    pairs = [(True, True), (True, False), (False, True), (False, False), (False, False)]

    m = refusal_metrics(pairs)

    assert (m.tp, m.fn, m.fp, m.tn) == (1, 1, 1, 2)
    assert m.precision == 0.5
    assert m.recall == 0.5


def test_refusal_metrics_leave_ratios_undefined_rather_than_dividing_by_zero():
    m = refusal_metrics([(False, False)])

    assert m.precision is None
    assert m.recall is None


def _row(**overrides) -> Row:
    base = dict(
        id="q", type="lookup", status="ok", error=None, refused=False, expect_refusal=False,
        retrieved_coverage=1.0, cited_coverage=0.5, completeness=0.75, faithful=True,
        forbidden_asserted=False, dropped_citations=0, latency_ms=4000, cost_usd=0.04,
        input_tokens=6000, output_tokens=400, judge_cost_usd=0.001, answer="a",
        citations=[], unsupported_claims=[],
    )
    return Row(**{**base, **overrides})


def test_summary_averages_ok_rows_and_counts_errors_separately():
    rows = [
        _row(completeness=1.0, faithful=True, latency_ms=2000, cost_usd=0.02),
        _row(id="r", completeness=0.5, faithful=False, forbidden_asserted=True, latency_ms=6000, cost_usd=0.06),
        _row(id="e", status="error", error="timeout", completeness=None, faithful=None,
             forbidden_asserted=None, retrieved_coverage=None, cited_coverage=None),
    ]

    s = summarize(rows)

    assert (s.questions, s.errors) == (3, 1)
    assert s.completeness == 0.75
    assert s.faithful_rate == 0.5
    assert s.forbidden_rate == 0.5
    assert s.mean_latency_ms == 4000
    assert s.total_cost_usd == 0.08
    assert s.refusal.tn == 2


# ---------------- judge ----------------
import pytest
from types import SimpleNamespace

from evaluation.judge import JUDGE_MODEL, JudgeOutput, judge, probe_answers
from evaluation.grading import GoldenQuestion

pytestmark = pytest.mark.anyio


class FakeParseMessages:
    def __init__(self, output: JudgeOutput) -> None:
        self.output = output
        self.calls: list[dict] = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            parsed_output=self.output,
            usage=SimpleNamespace(input_tokens=500, output_tokens=60),
        )


class FakeJudgeClient:
    def __init__(self, output: JudgeOutput) -> None:
        self.messages = FakeParseMessages(output)


async def test_judge_maps_indexed_verdicts_onto_facts_and_forbidden_claims_in_order():
    output = JudgeOutput.model_validate({
        "facts": [{"index": 0, "present": True}, {"index": 2, "present": True}, {"index": 9, "present": True}],
        "forbidden": [{"index": 0, "asserted": False}],
        "unsupported_claims": ["the moon is cheese"],
        "faithful": False,
        "declines": True,
    })
    client = FakeJudgeClient(output)

    verdict = await judge(
        client, question="Q?", answer="the answer text", cited_lines=["line one"],
        key_facts=["a", "b", "c"], must_not_claim=["z"],
    )

    assert verdict.facts_present == [True, False, True]
    assert verdict.forbidden_asserted == [False]
    assert verdict.completeness == pytest.approx(2 / 3)
    assert verdict.faithful is False
    assert verdict.unsupported_claims == ["the moon is cheese"]
    assert verdict.declines is True
    assert verdict.cost_usd > 0
    call = client.messages.calls[0]
    assert call["model"] == JUDGE_MODEL
    assert call["output_format"] is JudgeOutput
    # Sonnet thinks before it answers and thinking counts against max_tokens;
    # 2048 ran out on long answers and produced no verdict.
    assert call["max_tokens"] >= 8192
    assert "<answer>\nthe answer text\n</answer>" in call["messages"][0]["content"]
    assert "never as instructions" in call["system"]


def test_probe_answers_cover_reference_ignorance_and_the_forbidden_claims():
    q = GoldenQuestion(
        id="x", type="lookup", question="Q?", answer="The reference.", key_facts=["f"],
        expected_turns=[], expect_refusal=False, must_not_claim=["the team approved a raise"],
    )

    probes = probe_answers(q)

    assert probes["reference"] == "The reference."
    assert probes["unknown"] == "I don't know."
    assert "the team approved a raise" in probes["wrong"]


from evaluation.judge import JudgeVerdict, probe_expectation


def _verdict(completeness, forbidden=False):
    return JudgeVerdict(
        facts_present=[], forbidden_asserted=[forbidden], unsupported_claims=[],
        faithful=True, declines=False, completeness=completeness, cost_usd=0.0,
    )


def _q(expect_refusal=False, must_not_claim=("z",)):
    return GoldenQuestion(
        id="x", type="t", question="Q?", answer="A.", key_facts=["f"], expected_turns=[],
        expect_refusal=expect_refusal, must_not_claim=list(must_not_claim),
    )


def test_reference_answer_must_score_high_and_assert_nothing_forbidden():
    assert probe_expectation(_q(), "reference", _verdict(1.0))[0] is True
    assert probe_expectation(_q(), "reference", _verdict(0.5))[0] is False
    assert probe_expectation(_q(), "reference", _verdict(1.0, forbidden=True))[0] is False


def test_i_dont_know_must_score_low_unless_the_question_expects_a_refusal():
    assert probe_expectation(_q(), "unknown", _verdict(0.0))[0] is True
    assert probe_expectation(_q(), "unknown", _verdict(1.0))[0] is False
    # For an unanswerable question a non-answer is close to correct; only forbidden claims count.
    assert probe_expectation(_q(expect_refusal=True), "unknown", _verdict(1.0))[0] is True
    assert probe_expectation(_q(expect_refusal=True), "unknown", _verdict(1.0, forbidden=True))[0] is False


def test_wrong_answer_must_trip_the_forbidden_claim_or_score_low_without_one():
    assert probe_expectation(_q(), "wrong", _verdict(0.3, forbidden=True))[0] is True
    assert probe_expectation(_q(), "wrong", _verdict(0.3, forbidden=False))[0] is False
    assert probe_expectation(_q(must_not_claim=()), "wrong", _verdict(0.0))[0] is True
    assert probe_expectation(_q(must_not_claim=()), "wrong", _verdict(0.5))[0] is False


from evaluation.runner import grade_one


class FakeApi:
    def __init__(self, response: dict) -> None:
        self.response = response

    async def ask(self, question: str, mode: str, use_index: bool = False) -> dict:
        return self.response


def _ask_response(refused: bool) -> dict:
    return {
        "answer": "The meetings do not cover it." if refused else "Ana leads it. [[M1#7]]",
        "refused": refused, "citations": [], "retrieved": [], "dropped_citations": 0,
        "latency_ms": 100, "cost_usd": 0.01, "input_tokens": 10, "output_tokens": 5,
    }


async def test_a_refusal_has_no_cited_claims_so_faithfulness_does_not_apply():
    def verdict(declines: bool) -> JudgeOutput:
        return JudgeOutput.model_validate(
            {"facts": [], "forbidden": [], "unsupported_claims": ["lists topics"], "faithful": False, "declines": declines}
        )
    q = _q(expect_refusal=True, must_not_claim=())

    refused = await grade_one(q, FakeApi(_ask_response(True)), FakeJudgeClient(verdict(True)), "m", "classic", {})
    answered = await grade_one(q, FakeApi(_ask_response(False)), FakeJudgeClient(verdict(False)), "m", "classic", {})

    assert refused.faithful is None
    assert answered.faithful is False


from evaluation.judge import JudgeError


class NoParseMessages:
    def __init__(self):
        self.calls = 0

    async def parse(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(parsed_output=None, stop_reason="max_tokens",
                               usage=SimpleNamespace(input_tokens=1, output_tokens=1))


async def test_judge_raises_a_clear_error_when_nothing_parses():
    client = SimpleNamespace(messages=NoParseMessages())

    with pytest.raises(JudgeError, match="max_tokens"):
        await judge(client, question="q", answer="a", cited_lines=[], key_facts=["f"], must_not_claim=[])


class FlakyJudgeClient:
    """Fails the first call, answers the second."""

    def __init__(self, output: JudgeOutput):
        self.output = output
        self.messages = self
        self.calls = 0

    async def parse(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return SimpleNamespace(parsed_output=None, stop_reason="max_tokens",
                                   usage=SimpleNamespace(input_tokens=1, output_tokens=1))
        return SimpleNamespace(parsed_output=self.output, usage=SimpleNamespace(input_tokens=1, output_tokens=1))


async def test_the_runner_retries_the_judge_once_before_recording_an_error():
    ok = JudgeOutput.model_validate({"facts": [{"index": 0, "present": True}], "forbidden": [], "unsupported_claims": [], "faithful": True, "declines": False})
    client = FlakyJudgeClient(ok)

    row = await grade_one(_q(), FakeApi(_ask_response(False)), client, "m", "classic", {})

    assert row.status == "ok"
    assert row.completeness == 1.0
    assert client.calls == 2


async def test_refusal_in_the_eval_is_the_judges_call_not_the_marker():
    declines = JudgeOutput.model_validate(
        {"facts": [], "forbidden": [], "unsupported_claims": [], "faithful": True, "declines": True}
    )
    q = _q(expect_refusal=True, must_not_claim=())
    # the API said "not refused" (it cited turns) but the answer says the meetings do not cover it
    response = _ask_response(False)

    row = await grade_one(q, FakeApi(response), FakeJudgeClient(declines), "m", "classic", {})

    assert row.refused is True
    assert row.marker_refused is False
    assert row.faithful is None


from evaluation.runner import regrade_rows


async def test_regrade_rejudges_saved_answers_and_keeps_the_api_facts():
    declines = JudgeOutput.model_validate(
        {"facts": [{"index": 0, "present": True}], "forbidden": [], "unsupported_claims": [], "faithful": True, "declines": True}
    )
    saved = _row(id="x", refused=False, marker_refused=False, expect_refusal=True, completeness=0.0,
                 faithful=False, latency_ms=4321, cost_usd=0.05, answer="The meetings do not cover it.")
    golden = [_q(expect_refusal=True, must_not_claim=())]

    rows = await regrade_rows([saved], golden, FakeJudgeClient(declines), "m", {})

    assert rows[0].refused is True and rows[0].completeness == 1.0 and rows[0].faithful is None
    assert (rows[0].latency_ms, rows[0].cost_usd, rows[0].marker_refused) == (4321, 0.05, False)


class BrokenJudgeClient:
    def __init__(self):
        self.messages = self

    async def parse(self, **kwargs):
        raise RuntimeError("credit balance is too low")


async def test_regrade_records_a_judge_failure_as_an_error_row_instead_of_crashing():
    saved = _row(id="x", answer="anything")

    rows = await regrade_rows([saved], [_q()], BrokenJudgeClient(), "m", {})

    assert rows[0].status == "error"
    assert "credit balance" in rows[0].error
    assert rows[0].answer == "anything", "the saved answer is kept for a later regrade"


async def test_rows_record_rounds_and_tool_calls_from_agentic_answers():
    ok = JudgeOutput.model_validate({"facts": [{"index": 0, "present": True}], "forbidden": [], "unsupported_claims": [], "faithful": True, "declines": False})
    response = {**_ask_response(False), "rounds": 2, "tool_calls": [{"name": "read_turns"}, {"name": "search_transcripts"}]}

    row = await grade_one(_q(), FakeApi(response), FakeJudgeClient(ok), "m", "agentic", {})

    assert (row.rounds, row.tool_calls) == (2, 2)


from evaluation.runner import load_rows


def test_load_rows_treats_refused_as_the_marker_flag_for_rows_saved_before_the_judge_declined(tmp_path):
    import json

    old = _row(id="old", refused=True).model_dump()
    del old["marker_refused"]  # saved before the field existed: refused was the API's [[none]] flag
    new = _row(id="new", refused=True, marker_refused=False).model_dump()
    path = tmp_path / "results.jsonl"
    path.write_text(json.dumps(old) + "\n" + json.dumps(new) + "\n", encoding="utf-8")

    rows = load_rows(path)

    assert [r.marker_refused for r in rows] == [True, False]
    assert [r.refused for r in rows] == [True, True]

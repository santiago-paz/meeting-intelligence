"""Everything about a score that can be computed without a model.

Kept pure and unit-tested, because an eval whose arithmetic is wrong produces
confident numbers that point the wrong way.
"""

import json
from pathlib import Path
from statistics import mean

from pydantic import BaseModel


class ExpectedTurn(BaseModel):
    meeting: str
    turn: int
    quote: str


class GoldenQuestion(BaseModel):
    id: str
    type: str
    question: str
    answer: str
    key_facts: list[str]
    expected_turns: list[ExpectedTurn]
    expect_refusal: bool
    must_not_claim: list[str]


def load_golden(path: Path) -> list[GoldenQuestion]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [GoldenQuestion(**q) for q in data["questions"]]


def turn_coverage(
    expected: list[ExpectedTurn], retrieved: list[dict], citations: list[dict]
) -> tuple[float | None, float | None]:
    """Share of expected turns the system fetched, and share it actually cited."""
    if not expected:
        return None, None
    fetched = sum(
        1
        for e in expected
        if any(
            r["meeting_title"] == e.meeting and r["turn_start"] <= e.turn <= r["turn_end"]
            for r in retrieved
        )
    )
    cited = sum(
        1
        for e in expected
        if any(c["meeting_title"] == e.meeting and c["turn"] == e.turn for c in citations)
    )
    return fetched / len(expected), cited / len(expected)


class RefusalMetrics(BaseModel):
    tp: int
    fp: int
    fn: int
    tn: int
    precision: float | None
    recall: float | None


def refusal_metrics(pairs: list[tuple[bool, bool]]) -> RefusalMetrics:
    """pairs of (should have refused, did refuse). Refusing is the positive class."""
    tp = sum(1 for e, a in pairs if e and a)
    fp = sum(1 for e, a in pairs if not e and a)
    fn = sum(1 for e, a in pairs if e and not a)
    tn = sum(1 for e, a in pairs if not e and not a)
    return RefusalMetrics(
        tp=tp, fp=fp, fn=fn, tn=tn,
        precision=tp / (tp + fp) if tp + fp else None,
        recall=tp / (tp + fn) if tp + fn else None,
    )


class Row(BaseModel):
    """One graded question."""

    id: str
    type: str
    status: str  # ok | error
    error: str | None
    refused: bool
    expect_refusal: bool
    retrieved_coverage: float | None
    cited_coverage: float | None
    completeness: float | None
    faithful: bool | None
    forbidden_asserted: bool | None
    dropped_citations: int
    latency_ms: int
    cost_usd: float
    input_tokens: int
    output_tokens: int
    judge_cost_usd: float
    answer: str
    citations: list[dict]
    unsupported_claims: list[str]
    facts_present: list[bool] = []


class Summary(BaseModel):
    questions: int
    errors: int
    completeness: float | None
    faithful_rate: float | None
    forbidden_rate: float | None
    retrieved_coverage: float | None
    cited_coverage: float | None
    refusal: RefusalMetrics
    dropped_citations: int
    mean_latency_ms: int | None
    total_cost_usd: float
    judge_cost_usd: float


def _mean(values: list) -> float | None:
    values = [v for v in values if v is not None]
    return round(mean(values), 4) if values else None


def summarize(rows: list[Row]) -> Summary:
    ok = [r for r in rows if r.status == "ok"]
    return Summary(
        questions=len(rows),
        errors=len(rows) - len(ok),
        completeness=_mean([r.completeness for r in ok]),
        faithful_rate=_mean([float(r.faithful) for r in ok if r.faithful is not None]),
        forbidden_rate=_mean([float(r.forbidden_asserted) for r in ok if r.forbidden_asserted is not None]),
        retrieved_coverage=_mean([r.retrieved_coverage for r in ok]),
        cited_coverage=_mean([r.cited_coverage for r in ok]),
        refusal=refusal_metrics([(r.expect_refusal, r.refused) for r in ok]),
        dropped_citations=sum(r.dropped_citations for r in ok),
        mean_latency_ms=int(mean(r.latency_ms for r in ok)) if ok else None,
        total_cost_usd=round(sum(r.cost_usd for r in ok), 4),
        judge_cost_usd=round(sum(r.judge_cost_usd for r in ok), 4),
    )

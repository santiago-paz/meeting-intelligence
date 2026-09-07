"""Run the golden questions through the API and grade every answer."""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx2 as httpx

from evaluation.grading import GoldenQuestion, Row, Summary, summarize, turn_coverage
from evaluation.judge import JUDGE_MODEL, judge, probe_answers, probe_expectation


class Api:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=httpx.Timeout(180.0))

    async def close(self) -> None:
        await self._client.aclose()

    async def ask(self, question: str, mode: str, use_index: bool = False) -> dict:
        """POST /ask, retrying transport errors and 5xx twice with backoff."""
        delay = 2.0
        for attempt in range(3):
            try:
                response = await self._client.post(
                    "/ask", json={"question": question, "mode": mode, "use_index": use_index}
                )
            except httpx.TransportError as exc:
                if attempt == 2:
                    raise
                await asyncio.sleep(delay)
                delay *= 2
                continue
            if response.status_code >= 500 and attempt < 2:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            response.raise_for_status()
            return response.json()
        raise RuntimeError("unreachable")

    async def turns_by_meeting(self) -> dict[str, dict[int, dict]]:
        """title -> turn index -> turn, so cited turns can be shown to the judge."""
        meetings = (await self._client.get("/meetings")).json()
        result: dict[str, dict[int, dict]] = {}
        for meeting in meetings:
            detail = (await self._client.get(f"/meetings/{meeting['id']}")).json()
            result[meeting["title"]] = {t["idx"]: t for t in detail["turns"]}
        return result


def cited_lines(citations: list[dict], turns: dict[str, dict[int, dict]]) -> list[str]:
    lines = []
    for c in citations:
        turn = turns.get(c["meeting_title"], {}).get(c["turn"])
        text = turn["text"] if turn else "(turn not found)"
        lines.append(f"{c['meeting_title']} #{c['turn']} {c['speaker']} [{c['timestamp']}]: {text}")
    return lines


def _error_row(q: GoldenQuestion, error: str) -> Row:
    return Row(
        id=q.id, type=q.type, status="error", error=error, refused=False,
        expect_refusal=q.expect_refusal, retrieved_coverage=None, cited_coverage=None,
        completeness=None, faithful=None, forbidden_asserted=None, dropped_citations=0,
        latency_ms=0, cost_usd=0.0, input_tokens=0, output_tokens=0, judge_cost_usd=0.0,
        answer="", citations=[], unsupported_claims=[],
    )


async def grade_one(
    q: GoldenQuestion, api: Api, judge_client, judge_model: str, mode: str,
    turns: dict[str, dict[int, dict]], use_index: bool = False,
) -> Row:
    try:
        response = await api.ask(q.question, mode, use_index)
    except Exception as exc:  # noqa: BLE001 - every failure must land in the table
        return _error_row(q, f"ask: {type(exc).__name__}: {exc}")
    retrieved_cov, cited_cov = turn_coverage(q.expected_turns, response["retrieved"], response["citations"])
    verdict = None
    for attempt in range(2):  # one retry: a judge that parses nothing once is not a verdict
        try:
            verdict = await judge(
                judge_client,
                question=q.question,
                answer=response["answer"],
                cited_lines=cited_lines(response["citations"], turns),
                key_facts=q.key_facts,
                must_not_claim=q.must_not_claim,
                model=judge_model,
            )
            break
        except Exception as exc:  # noqa: BLE001
            if attempt == 1:
                return _error_row(q, f"judge: {type(exc).__name__}: {exc}")
    return Row(
        id=q.id, type=q.type, status="ok", error=None,
        refused=response["refused"], expect_refusal=q.expect_refusal,
        retrieved_coverage=retrieved_cov, cited_coverage=cited_cov,
        completeness=verdict.completeness,
        # Faithfulness is about cited claims; a refusal makes none. The
        # forbidden-claim check still catches a refusal that invents things.
        faithful=None if response["refused"] else verdict.faithful,
        forbidden_asserted=any(verdict.forbidden_asserted) if q.must_not_claim else False,
        dropped_citations=response["dropped_citations"], latency_ms=response["latency_ms"],
        cost_usd=response["cost_usd"], input_tokens=response["input_tokens"],
        output_tokens=response["output_tokens"], judge_cost_usd=verdict.cost_usd,
        answer=response["answer"], citations=response["citations"],
        unsupported_claims=verdict.unsupported_claims, facts_present=verdict.facts_present,
    )


async def run(
    golden: list[GoldenQuestion], *, api_url: str, mode: str, judge_client,
    judge_model: str = JUDGE_MODEL, concurrency: int = 3, out_root: Path, use_index: bool = False,
) -> tuple[list[Row], Summary, Path]:
    api = Api(api_url)
    semaphore = asyncio.Semaphore(concurrency)
    variant = f"{mode}-index" if use_index else mode
    out_dir = out_root / f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{variant}"
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "results.jsonl"
    started = time.monotonic()
    try:
        turns = await api.turns_by_meeting()

        async def one(q: GoldenQuestion) -> Row:
            async with semaphore:
                row = await grade_one(q, api, judge_client, judge_model, mode, turns, use_index)
            with results_path.open("a", encoding="utf-8") as f:
                f.write(row.model_dump_json() + "\n")
            print(format_row(row), flush=True)
            return row

        print(format_header(), flush=True)
        rows = list(await asyncio.gather(*(one(q) for q in golden)))
    finally:
        await api.close()
    rows.sort(key=lambda r: [q.id for q in golden].index(r.id))
    summary = summarize(rows)
    (out_dir / "summary.json").write_text(
        json.dumps({
            "mode": mode, "use_index": use_index, "judge_model": judge_model, "api_url": api_url,
            "wall_seconds": round(time.monotonic() - started, 1),
            **summary.model_dump(),
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    return rows, summary, out_dir


def _pct(value: float | None) -> str:
    return "  -  " if value is None else f"{value * 100:4.0f}%"


def _flag(value: bool | None) -> str:
    return " - " if value is None else (" y " if value else " n ")


def format_header() -> str:
    return (
        f"{'question':<34} {'type':<12} {'refuse':<7} {'compl':>5} {'faith':>5} {'forb':>5}"
        f" {'retr':>5} {'cited':>5} {'drop':>4} {'ms':>6} {'$':>7}"
    )


def format_row(r: Row) -> str:
    if r.status == "error":
        return f"{r.id:<34} {r.type:<12} ERROR {r.error}"
    refuse = ("Y" if r.refused else "n") + "/" + ("Y" if r.expect_refusal else "n")
    return (
        f"{r.id:<34} {r.type:<12} {refuse:<7} {_pct(r.completeness)} {_flag(r.faithful)}"
        f" {_flag(r.forbidden_asserted)} {_pct(r.retrieved_coverage)} {_pct(r.cited_coverage)}"
        f" {r.dropped_citations:>4} {r.latency_ms:>6} {r.cost_usd:>7.4f}"
    )


def format_summary(s: Summary, mode: str) -> str:
    refusal = s.refusal
    return "\n".join([
        f"== {mode} == {s.questions} questions, {s.errors} errors",
        f"completeness {_pct(s.completeness).strip():>5}   faithful (answered only) {_pct(s.faithful_rate).strip():>5}"
        f"   forbidden asserted {_pct(s.forbidden_rate).strip():>5}",
        f"retrieved coverage {_pct(s.retrieved_coverage).strip():>5}   cited coverage {_pct(s.cited_coverage).strip():>5}"
        f"   dropped citations {s.dropped_citations}",
        f"refusal precision {_pct(refusal.precision).strip():>5}   recall {_pct(refusal.recall).strip():>5}"
        f"   (tp {refusal.tp} fp {refusal.fp} fn {refusal.fn} tn {refusal.tn})",
        f"mean latency {s.mean_latency_ms} ms   answer cost ${s.total_cost_usd:.4f}   judge cost ${s.judge_cost_usd:.4f}",
    ])


async def check_judge(golden: list[GoldenQuestion], judge_client, judge_model: str, count: int = 6) -> bool:
    """Feed the judge known answers; a judge that passes a wrong answer is broken."""
    chosen: list[GoldenQuestion] = []
    for wanted in ("lookup", "aggregation", "temporal", "speaker", "injection", "unanswerable"):
        chosen.extend([q for q in golden if q.type == wanted][:1])
    chosen = chosen[:count]
    all_ok = True
    print(f"{'question':<30} {'probe':<10} {'compl':>5} {'forb':>5} {'faith':>5}  expectation")
    for q in chosen:
        lines = [f"{e.meeting} #{e.turn}: {e.quote}" for e in q.expected_turns]
        for name, answer in probe_answers(q).items():
            verdict = await judge(
                judge_client, question=q.question, answer=answer, cited_lines=lines,
                key_facts=q.key_facts, must_not_claim=q.must_not_claim, model=judge_model,
            )
            forbidden = any(verdict.forbidden_asserted)
            ok, expectation = probe_expectation(q, name, verdict)
            all_ok &= ok
            print(
                f"{q.id:<30} {name:<10} {_pct(verdict.completeness)} {_flag(forbidden)}"
                f" {_flag(verdict.faithful)}  {'PASS' if ok else 'FAIL'}: {expectation}"
            )
    return all_ok

"""Run the golden questions through the API and print the scorecard.

    uv run python eval.py --mode classic
    uv run python eval.py --check-judge        # probe the judge with known answers first

Needs the API running (docker compose up -d db; uv run uvicorn app.main:app)
and ANTHROPIC_API_KEY in api/.env for the judge.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from anthropic import AsyncAnthropic

from app.settings import Settings
from evaluation.grading import load_golden
from evaluation.judge import JUDGE_MODEL
from evaluation.runner import check_judge, format_summary, regrade, run

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", default="classic", choices=["classic", "agentic"])
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--judge-model", default=JUDGE_MODEL)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--only", help="comma-separated question ids")
    parser.add_argument("--golden", default=str(ROOT / "fixtures" / "golden.json"))
    parser.add_argument("--out", default=str(ROOT / "eval-runs"))
    parser.add_argument("--check-judge", action="store_true", help="probe the judge, run nothing else")
    parser.add_argument("--index", action="store_true", help="put the extracted rows into the prompt (off by default, see design doc)")
    parser.add_argument("--regrade", metavar="RUN_DIR", help="re-judge a saved run without asking the API again")
    args = parser.parse_args()

    settings = Settings()
    if not settings.anthropic_api_key:
        print("ANTHROPIC_API_KEY is not set in api/.env; the judge needs it.", file=sys.stderr)
        return 2
    judge_client = AsyncAnthropic(api_key=settings.anthropic_api_key, base_url=settings.claude_base_url)
    golden = load_golden(Path(args.golden))
    if args.only:
        wanted = set(args.only.split(","))
        golden = [q for q in golden if q.id in wanted]

    if args.check_judge:
        ok = asyncio.run(check_judge(golden, judge_client, args.judge_model))
        print("\njudge check:", "PASS" if ok else "FAIL")
        return 0 if ok else 1

    if args.regrade:
        rows, summary, out_dir = asyncio.run(
            regrade(Path(args.regrade), golden, api_url=args.api, judge_client=judge_client, judge_model=args.judge_model)
        )
        print(format_summary(summary, f"regraded {Path(args.regrade).name}"))
        print(f"\nrows: {out_dir / 'results.jsonl'}")
        return 0

    rows, summary, out_dir = asyncio.run(
        run(
            golden, api_url=args.api, mode=args.mode, judge_client=judge_client,
            judge_model=args.judge_model, concurrency=args.concurrency, out_root=Path(args.out),
            use_index=args.index,
        )
    )
    print()
    print(format_summary(summary, f"{args.mode} (with index)" if args.index else args.mode))
    print(f"\nrows: {out_dir / 'results.jsonl'}\nsummary: {out_dir / 'summary.json'}")
    return 1 if summary.errors else 0


if __name__ == "__main__":
    sys.exit(main())

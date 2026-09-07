# Eval runs

One directory per run of `api/eval.py`: `results.jsonl` has one graded row per
question, `summary.json` the aggregates. Directory names end in the variant.
`classic` is classic mode without the extracted index (the default),
`classic-index` is the same with the index in the prompt, `agentic` is the
model-driven mode. Numbers move a few
points between runs of the same variant; compare variants across at least two
runs each.

| Run | Seed | Variant | Note |
| --- | --- | --- | --- |
| 093214-classic-oldkey | 1 | classic | Before the golden key correction (22 questions). Kept for the record, not comparable. |
| 093939-classic | 1 | classic | Baseline, corrected key. |
| 094214-classic | 1 | classic | Baseline, second run. |
| 103147-classic-index-v1 | 2 | classic + index | First index prompt. One judge error (fixed later by raising the judge's output budget). |
| 103347-classic-index-v1 | 2 | classic + index | First index prompt, second run. |
| 103927-classic | 2 | classic | Same seed as the index runs, so retrieval is identical. |
| 104043-classic | 2 | classic | Second run. |
| 104148-classic-index | 2 | classic + index | Index prompt with the summary rules. |
| 104318-classic-index | 2 | classic + index | Second run; one judge error, since fixed. |
| 105800-agentic | 2 | agentic | First agentic run; judge without the `declines` field. |
| 110145-agentic | 2 | agentic | Second agentic run, same judge. |
| 125811-agentic | 2 | agentic | Citing rule in the prompt (cite every turn a sentence draws on); current judge. |
| 130035-agentic | 2 | agentic | Second run with the citing rule. |
| `*-regraded` | | | The run they are named after, re-judged with the current judge. Compare these, never the originals, with 125811 and later. |

Seed 1 and seed 2 are the same five transcripts ingested twice. Re-ingesting
regenerates the context headers, which changes what retrieval returns; that
is why the injection question is answered on seed 1 and refused on seed 2.

Runs up to and including 110145 were judged before the judge had the
`declines` field: their refusal column follows the API's `[[none]]` marker and
their faithfulness counts refusals as answers. The four `-regraded`
directories hold the same answers re-judged with the current judge
(`api/eval.py --regrade <run>`); answers, citations, latency and cost are
copied and only the verdicts change. Re-judging identical answers flipped one
to four faithfulness verdicts per run out of seventeen or eighteen, so a
faithfulness gap under about twelve points is noise.

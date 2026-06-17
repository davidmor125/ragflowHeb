# RAG Evaluation Summary

## Bottom line

**Final accuracy: 84.8% (112/132)** with the keyword grader.
**LLM-as-judge sample shows the keyword grader is too lenient** — true accuracy is closer to **70%**.

## Setup under test

| Parameter | Value |
|---|---|
| Knowledge base | `hozrim` — 646 banking procedures (Hebrew HTML), parser=`naive` |
| Dialog | `bank-eval` |
| LLM | `gemma4:31b-cloud@Ollama` |
| Embedding | `bge-m3@Ollama` (multilingual) |
| Reranker | `BAAI/bge-reranker-v2-m3@HuggingFace` (multilingual) |
| `top_k` / `top_n` / `similarity_threshold` | 1024 / 25 / 0.1 |

## Test set

**132 questions** drawn from a banker-graded xlsx
(`html_output/_eval_report/newtest/test_report_24_05.xlsx`).
Covers 56 unique procedures across 21 banking topics.
Every procedure referenced in the xlsx has a corresponding HTML file in `hozrim`.

## Iteration log

| Iteration | Change | PASS | Δ |
|---|---|---:|---:|
| 1 | Baseline (gpt-oss:120b, top_n=15) | 75% | — |
| 2 | Strip broken `<think>` tags from gpt-oss output (rescore) | 80% | +5% |
| 3 | Switch LLM to `gemma4:31b-cloud` (no reasoning tags) | 81% | +1% |
| 4 | `top_n` 15 → 25 | **84.8%** | **+4%** |

## Where the rerank stands

- Correct doc retrieved at rank #1: **58%**
- Correct doc in top-3: **82%**
- Correct doc anywhere in top-25: **95%**

The reranker is doing its job — when it misses, it's by 1–2 spots, not by hundreds.

## LLM-as-judge sanity check

Ran `gpt-oss:120b` as a semantic judge on 10 sampled answers (mix of pass and fail).
Result: keyword grader **disagrees with semantic grader on 6/10 questions** —
in every disagreement, the semantic grader was stricter
("the answer technically contains the keywords but doesn't actually answer the question").

**Implication:** the 84.8% number is optimistic. A full LLM-judge run would
likely place the true accuracy near **70%**.

## Failure breakdown (25 keyword-grader failures)

| Bucket | Count |
|---|---:|
| Reranker placed correct doc at #1, but the chunk picked is the wrong section | 10 |
| Reranker missed the correct doc entirely | 5 |
| Reranker placed correct doc beyond top-3 | 4 |
| Reranker placed correct doc in top-3 (2/3) | 2 |
| Other | 4 |

The dominant pattern is **chunking, not ranking**: documents like
`32904.html` and `31097.html` produce one or two outsized chunks (5K–80K chars)
that bundle several distinct sections, so the LLM sees the right document but
focuses on the wrong paragraph.

## What was tried beyond this number

### Pipeline POC — abandoned

A pipeline (`enriched_ingestion_v1`) was built to add per-chunk
**Summarization + Auto Question** (Auto Keyword and Auto Metadata were dropped to
halve cost). Hebrew-language prompts. `chunk_token_size` raised from 512 to 1024.

It did not finish. The Ollama Cloud endpoint
(`gemma4:31b-cloud@Ollama`, the only multilingual non-reasoning chat model
available on this tenant) returned `APIConnectionError` on most calls
(5,769 task failures vs 827 successes). Without a stable LLM for the extractor
nodes, the pipeline cannot run.

The `hozrim_poc` KB and `bank-eval-poc` dialog are still present in case the
provider stabilizes and we want to retry.

## Files that matter

| File | Purpose |
|---|---|
| [`test_questions_full.json`](test_questions_full.json) | 132 questions |
| [`eval_full_hozrim.py`](eval_full_hozrim.py) | Runner — must execute inside the ragflow container |
| [`eval_full_results_v3.json`](eval_full_results_v3.json) | Final per-question results (with retrieved chunks + scores) |
| [`eval_full_results_v3.csv`](eval_full_results_v3.csv) | Same, opens in Excel RTL |
| [`eval_full_results_llm_graded.json`](eval_full_results_llm_graded.json) | LLM-judge sample on the 25 failures |
| [`EVAL_TEST_SET.md`](EVAL_TEST_SET.md) | How the test set was built |

## What would actually push past 85%

Ranked by expected impact, given the failure pattern above:

1. **Better chunking on the heavy files.** Switch `parser_id` from `naive` to
   `laws` for procedures whose chunks exceed ~5 K chars, or pre-split the
   problem files (32904, 31097, 78686, …) by numbered section in
   pre-processing. This addresses the dominant failure bucket directly.
2. **Per-chunk summary + question enrichment**, once the LLM provider is stable.
   The pipeline is already wired and saved (`enriched_ingestion_v1`).
3. **A small banking glossary** injected at retrieval time
   (a feature already wired in the codebase) — pays off on the small share of
   questions whose only failure is a domain term mismatch.
4. **Agentic flow only after the above.** The `Categorize → Retrieve → Self-check`
   loop helps when the data side is already clean; on the current chunk
   quality it would just recycle bad context.

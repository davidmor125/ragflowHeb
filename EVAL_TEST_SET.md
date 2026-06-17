# Eval Test Set — Banking Procedures RAG

## Overview

Evaluation test set for RAGFlow retrieval/answer quality on Israeli bank
procedural documents.

## Source

Questions are derived from the QA-by-bankers spreadsheet:

```
c:\develop\html_output\_eval_report\newtest\test_report_24_05.xlsx
```

The xlsx (sheet `גיליון1`, "בדיקות צ'אטבוט בנוח") contains 137 rows of
manually-graded chatbot tests. We extract every row that has both a
procedure number (`מס' נוהל שנבדק`, column B) and a question (column E),
yielding **132 questions across 56 unique procedures and 21 topics**.

## Files

| File | Description |
|---|---|
| `test_questions_full.json` | All 132 questions (curated). Built by `_build_full_test_set.py` from the xlsx. |
| `test_questions_dataset_aligned.json` | Earlier 10-question subset for the small `test_five_files` KB. |
| `eval_full_hozrim.py` | The runner. Runs every question through dialog `bank-eval` and writes results. Run **inside the ragflow container**. |
| `eval_full_results.json` | Detailed run output (per-question chunks, scores, verdict). |
| `eval_full_results.csv` | Same data as Excel-friendly CSV with Hebrew column headers. |

## Question record schema (`test_questions_full.json`)

```json
{
  "row": 5,                    // row index in the source xlsx
  "procedure": "32328",        // procedure number — also the HTML filename stem
  "topic": "אבטחת מידע",       // top-level category from the xlsx
  "subtopic": "...",
  "question": "...",
  "expected_answer": "...",    // the bank's gold answer
  "source_file": "טסט/32328.html"  // resolved path inside the hozrim KB
}
```

## How to run

The runner is meant to execute *inside* the `docker-ragflow-cpu-1`
container so it can use the `api.db.services.dialog_service.async_chat`
path (the same code the UI uses).

```powershell
# Copy script + question file into the container
docker cp test_questions_full.json docker-ragflow-cpu-1:/ragflow/
docker cp eval_full_hozrim.py      docker-ragflow-cpu-1:/ragflow/

# Run (tolerates being killed; saves results incrementally)
docker exec -e PYTHONIOENCODING=utf-8 -w /ragflow docker-ragflow-cpu-1 `
  python eval_full_hozrim.py

# Pull results out
docker cp docker-ragflow-cpu-1:/ragflow/eval_full_results.json .
docker cp docker-ragflow-cpu-1:/ragflow/eval_full_results.csv  .
```

## Dialog under test: `bank-eval`

| Setting | Value |
|---|---|
| `id` | `cf68bf1a46f011f196f633ac796a3d7a` |
| `kb_ids` | `dc0091ca46e211f196f633ac796a3d7a` (`hozrim`, 646 docs, parser=`naive`) |
| `llm_id` | `gpt-oss:120b-cloud@Ollama` |
| `rerank_id` | `BAAI/bge-reranker-v2-m3@HuggingFace` |
| `top_k` | `1024` |
| `top_n` | `15` |
| `similarity_threshold` | `0.1` |
| `vector_similarity_weight` | `0.3` |
| `prompt_config` | copied from `bank-eval-clean` |

These match `bank-eval-clean` (the dialog used for the 10-question subset
on `test_five_files`) on every retrieval/prompt parameter; only `llm_id`
and `kb_ids` differ by design.

## Grading

Per-question we capture and report:

- **Answer PASS/FAIL** — keyword-overlap heuristic. Pulls 8 distinctive
  tokens from `expected_answer` (Hebrew stopwords filtered) and passes if
  ≥25% appear in the system answer. Short gold answers ("כן", "3") are
  matched literally.
- **Reranker PASS/FAIL** — does the chunk from the *correct* procedure
  file appear anywhere in the top-`top_n` retrieved chunks?
- **Rank of correct doc** — its position in the retrieved list.
- **Top score / matched score** — the rerank similarity scores.
- **Top-5 chunks** snapshot for failure analysis.

The CSV has Hebrew column headers and UTF-8 BOM so it opens in Excel
right-to-left.

## Notes

- The `xlsx` has 137 rows; 5 are header / scoring legend / a row without
  a procedure number, leaving 132 testable questions.
- Skipping behavior (`Skipped: 0`) means every procedure mentioned in the
  xlsx exists as a file in `hozrim`. There is no dataset gap on this run.
- The earlier 10-question subset run is unaffected — `test_five_files`
  remains intact for the focused diagnosis work.

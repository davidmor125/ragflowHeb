#!/usr/bin/env python3
"""Evaluate the bank's reference Q&A spreadsheet against gemma4:26b.

Input:
  - test_report_24_05.xlsx with one Q per row, plus a 'מס' נוהל' column
    that names the HTML file holding the source procedure.
  - A directory of <נוהל>.html files.

For each row we:
  1. Look up the HTML file by נוהל number.
  2. Extract its text via the project's RAGFlowHtmlParser (so we exercise
     the same Hebrew-aware path the production ingest uses).
  3. Ask gemma4:26b to answer the question using ONLY the procedure text.
  4. Ask gemma4:26b (LLM-as-judge) to grade the answer against the human
     gold answer as: תקין / חלקי / לא תקין.
  5. Write the model's answer into 'תשובת המערכת' (col 5) and the verdict
     into 'מענה תקין/לא תקין/חלקי' (col 9) — an in-place fill of the
     existing Excel template.

UTF-8 throughout. The Excel keeps its original formatting (we use a
non-read-only load + .save). Saves after every row so an interruption never
loses progress.

Usage:
    python tools/scripts/eval_excel_qa.py \\
        --xlsx C:/develop/html_output/_eval_report/newtest/test_report_24_05.xlsx \\
        --html-dir C:/develop/html_output/_eval_report/newtest/טסט \\
        --out C:/develop/html_output/_eval_report/newtest/test_report_24_05_filled.xlsx
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import openpyxl

# UTF-8 stdout so logs in Hebrew don't crash on Windows cp1252 consoles.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# Reuse the same primitives we built for the HTML eval. Same model, same
# Ollama config, same UTF-8 request shape — keeps results comparable.
from tools.scripts.eval_html_qa import (  # noqa: E402
    OLLAMA_MODEL,
    OLLAMA_URL,
    NUM_PREDICT_ANSWER,
    NUM_PREDICT_JUDGE,
    extract_json,
    extract_text_from_html,
    ollama_generate,
)


# Bank procedure docs are big (median 28K, p95 125K, max 190K chars).
# truncate_doc from eval_html_qa caps at 12K which throws away most of every
# document and made the smoke-test return "לא נמצא בנוהל" for answers that
# clearly were in the file. We replace it with question-aware windowing:
# pick the chunk(s) that contain the question's keywords. This keeps gemma's
# context window within reason while ensuring the relevant section is shown.

DOC_WINDOW_CHARS = 60000      # how much we send to the model per question
CHUNK_SIZE = 4000             # ranking unit
CHUNK_OVERLAP = 500           # so a sentence on a chunk boundary stays whole
MIN_TOTAL_KEYWORD_HITS = 3    # below this we send the whole doc head — chunking is unreliable
HEBREW_STOPWORDS = {
    "של", "על", "את", "אל", "מן", "כי", "לא", "הוא", "היא", "הם", "הן",
    "זה", "זו", "מה", "כמה", "איך", "מתי", "איפה", "מי", "האם", "כיצד",
    "במה", "במידה", "באיזה", "באיזו", "מהו", "מהי", "מהם", "ניתן", "יש",
    "אין", "עם", "ללא", "אך", "אבל", "כך", "לכן", "וגם", "וכן",
    "ה", "ו", "ב", "ל", "מ", "ש",
}


def _select_doc_window(text: str, question: str,
                       window_chars: int = DOC_WINDOW_CHARS,
                       chunk_size: int = CHUNK_SIZE,
                       overlap: int = CHUNK_OVERLAP) -> str:
    """Return up to ``window_chars`` of text most likely to answer the question.

    Splits the document into overlapping windows, scores each by keyword
    overlap with the (stopword-filtered) question terms, and concatenates the
    top-N windows in original document order. Falls back to the document's
    head when the question shares no keywords with any chunk."""
    if len(text) <= window_chars:
        return text

    # Split into overlapping chunks.
    chunks: list[tuple[int, str]] = []  # (start_pos, text)
    pos = 0
    step = chunk_size - overlap
    while pos < len(text):
        chunks.append((pos, text[pos:pos + chunk_size]))
        pos += step

    # Tokenize the question into keywords (length>=2, not stopwords).
    import re
    raw_tokens = re.findall(r"[֐-׿\w]+", question.lower())
    keywords = [t for t in raw_tokens if len(t) >= 2 and t not in HEBREW_STOPWORDS]
    if not keywords:
        return text[:window_chars]

    # Score each chunk by raw keyword hit count (case-insensitive).
    scored: list[tuple[int, int, str]] = []  # (-score, start_pos, chunk)
    total_hits = 0
    for start, chunk in chunks:
        chunk_lower = chunk.lower()
        score = sum(chunk_lower.count(kw) for kw in keywords)
        total_hits += score
        scored.append((-score, start, chunk))

    # If keyword matching is too weak across the whole doc, ranking is
    # unreliable — fall back to sending the document head (which is
    # almost always the table of contents + opening definitions, the most
    # context-bearing part of a Hebrew banking procedure).
    if total_hits < MIN_TOTAL_KEYWORD_HITS:
        return text[:window_chars]

    # Pick top chunks until we fill the window. Re-sort selected chunks by
    # original position so the model reads them in document order.
    scored.sort()
    selected: list[tuple[int, str]] = []
    total = 0
    for neg_score, start, chunk in scored:
        if neg_score == 0:
            break  # No more relevant chunks.
        if total + len(chunk) > window_chars:
            break
        selected.append((start, chunk))
        total += len(chunk) + 4  # +4 for the "...\n" separator below
    if not selected:
        # No keyword hit — fall back to the head of the document.
        return text[:window_chars]
    selected.sort()
    return "\n...\n".join(c for _, c in selected)


def select_doc_for_question(text: str, question: str) -> str:
    """Public wrapper used by evaluate_row."""
    return _select_doc_window(text, question)

# We need a 3-class verdict (תקין / חלקי / לא תקין), not the binary PASS/FAIL
# the original script used. Custom prompt below.
PROMPT_JUDGE_3CLASS = """אתה שופט תשובות. בהינתן שאלה, תשובה רצויה (gold) שניתנה ע"י מומחה, ותשובה של מודל, החלט באיזו רמה תשובת המודל נכונה.

אפשרויות:
- "תקין": תשובת המודל מדויקת ומכסה את עיקר תשובת הזהב.
- "חלקי": תשובת המודל נכונה חלקית, חסרים פרטים מהותיים, או מנוסחת באופן שמותיר ספק.
- "לא תקין": תשובת המודל שגויה עובדתית, או שאינה עונה על השאלה כלל.

החזר JSON תקני בלבד בצורה: {{"verdict": "תקין" | "חלקי" | "לא תקין", "reason": "סיבה קצרה אם חלקי או לא תקין"}}

שאלה: {q}
תשובת זהב: {gold}
תשובת המודל: {actual}
"""

# Excel column indices (0-based).
COL_NOHEL = 1
COL_QUESTION = 4
COL_MODEL_ANSWER = 5
COL_GOLD_ANSWER = 6
COL_VERDICT = 9
HEADER_ROW = 4  # rows 0-3 are titles + legend
FIRST_DATA_ROW = 5

REANSWER_NUM_PREDICT = 3000  # Some rows need bigger budgets after thinking.

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("eval_excel_qa")


PROMPT_ANSWER_BANK = """ענה על השאלה הבאה אך ורק על סמך הטקסט שלהלן (נוהל בנקאי). אם התשובה לא מופיעה בטקסט, ענה: "לא נמצא בנוהל".

תן תשובה קצרה ותכליתית בעברית. אל תוסיף הסברים מיותרים.

טקסט הנוהל:
\"\"\"
{doc}
\"\"\"

שאלה: {q}

תשובה:"""


def evaluate_row(question: str, gold: str, html_path: Path, text_cache: dict) -> tuple[str, str, str]:
    """Return (model_answer, verdict, reason). Verdict is one of:
        "תקין" | "חלקי" | "לא תקין" | "ERROR"
    """
    if html_path.name not in text_cache:
        try:
            text_cache[html_path.name] = extract_text_from_html(html_path)
        except Exception as e:
            return "", "ERROR", f"extract failed: {e}"
    # Question-aware window: pick the part of the procedure most likely
    # to contain the answer instead of slicing off the head + tail.
    doc = select_doc_for_question(text_cache[html_path.name], question)

    # Step 1: ask the model.
    try:
        answer = ollama_generate(
            PROMPT_ANSWER_BANK.format(doc=doc, q=question),
            num_predict=NUM_PREDICT_ANSWER,
        ).strip()
    except Exception as e:
        return "", "ERROR", f"answer call failed: {e}"

    if not answer:
        # Retry once with a larger token budget — Gemma's thinking phase
        # sometimes eats the entire NUM_PREDICT_ANSWER and emits nothing
        # visible. The HTML-QA eval saw this on ~2% of items.
        try:
            answer = ollama_generate(
                PROMPT_ANSWER_BANK.format(doc=doc, q=question),
                num_predict=REANSWER_NUM_PREDICT,
            ).strip()
        except Exception as e:
            return "", "ERROR", f"answer retry failed: {e}"
        if not answer:
            return "", "ERROR", "model returned empty answer twice"

    # Step 2: judge.
    try:
        judge_raw = ollama_generate(
            PROMPT_JUDGE_3CLASS.format(q=question, gold=gold, actual=answer),
            num_predict=NUM_PREDICT_JUDGE * 3,  # 3-class verdict + Hebrew reason; thinking eats ~300.
        )
        judge = extract_json(judge_raw)
        verdict = str(judge.get("verdict", "")).strip()
        reason = str(judge.get("reason", "")).strip()
        if verdict not in ("תקין", "חלקי", "לא תקין"):
            return answer, "ERROR", f"unparseable verdict: {judge_raw[:120]!r}"
    except Exception as e:
        return answer, "ERROR", f"judge failed: {e}"

    return answer, verdict, reason


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--xlsx", required=True, type=Path, help="input Excel template")
    p.add_argument("--html-dir", required=True, type=Path, help="directory of <נוהל>.html files")
    p.add_argument("--out", required=True, type=Path, help="output Excel path (separate from input)")
    p.add_argument("--limit", type=int, default=0, help="stop after N rows (0 = all)")
    p.add_argument("--start-row", type=int, default=FIRST_DATA_ROW,
                   help=f"0-based row index to start from (default {FIRST_DATA_ROW}). Useful for resuming.")
    p.add_argument("--skip-filled", action="store_true",
                   help="skip rows that already have a model answer (for resuming a partial run)")
    args = p.parse_args()

    if not args.xlsx.is_file():
        log.error(f"missing xlsx: {args.xlsx}")
        return 2
    if not args.html_dir.is_dir():
        log.error(f"missing html dir: {args.html_dir}")
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)

    # Load with formatting preserved (NOT read_only).
    wb = openpyxl.load_workbook(args.xlsx)
    ws = wb.active
    log.info(f"workbook: sheet={ws.title!r} rows={ws.max_row}")

    # Drop embedded images (typically the bank logo). openpyxl can't re-save
    # them reliably from a re-loaded workbook, and the output Excel doesn't
    # need the logo — only the answers and verdicts. Per user direction:
    # don't touch images, just remove them.
    for s in wb.worksheets:
        if hasattr(s, "_images"):
            s._images = []

    text_cache: dict[str, str] = {}  # filename → extracted text (avoid re-parsing for repeats)
    counts = {"תקין": 0, "חלקי": 0, "לא תקין": 0, "ERROR": 0, "SKIPPED": 0}

    rows_processed = 0
    t0 = time.time()
    # openpyxl is 1-indexed; we convert. Iterate by row index so we can write back.
    for excel_row_idx in range(args.start_row + 1, ws.max_row + 1):  # +1 for openpyxl 1-index
        row = [ws.cell(row=excel_row_idx, column=ci + 1).value for ci in range(ws.max_column)]
        nohel = row[COL_NOHEL]
        question = row[COL_QUESTION]
        gold = row[COL_GOLD_ANSWER]
        existing_answer = row[COL_MODEL_ANSWER]
        if not nohel or not question:
            continue  # blank row
        if args.skip_filled and existing_answer:
            counts["SKIPPED"] += 1
            continue

        nohel_str = str(nohel).strip()
        question = str(question).strip()
        gold = (str(gold).strip() if gold else "")

        html_path = args.html_dir / f"{nohel_str}.html"
        if not html_path.exists():
            log.warning(f"  row {excel_row_idx}: HTML not found: {html_path.name}")
            ws.cell(row=excel_row_idx, column=COL_MODEL_ANSWER + 1).value = ""
            ws.cell(row=excel_row_idx, column=COL_VERDICT + 1).value = "ERROR: missing HTML"
            counts["ERROR"] += 1
            wb.save(args.out)
            continue

        log.info(f"  row {excel_row_idx} (נוהל={nohel_str}): {question[:60]}…")
        t_row = time.time()
        answer, verdict, reason = evaluate_row(question, gold, html_path, text_cache)
        elapsed = time.time() - t_row

        ws.cell(row=excel_row_idx, column=COL_MODEL_ANSWER + 1).value = answer
        # Verdict cell shows the verdict + reason if the model partially failed.
        if verdict in ("חלקי", "לא תקין") and reason:
            ws.cell(row=excel_row_idx, column=COL_VERDICT + 1).value = f"{verdict} — {reason}"
        else:
            ws.cell(row=excel_row_idx, column=COL_VERDICT + 1).value = verdict

        counts[verdict if verdict in counts else "ERROR"] += 1
        log.info(f"    → {verdict} ({elapsed:.1f}s)")

        # Save every row so a kill never loses progress.
        wb.save(args.out)

        rows_processed += 1
        if args.limit > 0 and rows_processed >= args.limit:
            log.info(f"hit --limit={args.limit}, stopping")
            break

    total_time = time.time() - t0
    log.info("=" * 60)
    log.info(f"DONE in {total_time:.1f}s — {rows_processed} rows processed")
    log.info(f"  תקין:    {counts['תקין']}")
    log.info(f"  חלקי:    {counts['חלקי']}")
    log.info(f"  לא תקין: {counts['לא תקין']}")
    log.info(f"  ERROR:   {counts['ERROR']}")
    log.info(f"  SKIPPED: {counts['SKIPPED']}")
    log.info(f"output: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

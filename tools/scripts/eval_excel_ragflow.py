#!/usr/bin/env python3
"""Evaluate the bank's Q&A spreadsheet against the *real* RAGFlow pipeline.

Unlike eval_excel_qa.py (which talks to ollama directly and bypasses RAGFlow's
retrieval), this script exercises the full production stack:

  Excel question
    → POST /api/v1/openai/<chat_id>/chat/completions
        → RAGFlow does:
            keyword extraction → vector search (embeddings) → reranker
            → top-K chunks → LLM (gemma4) with retrieved context → answer
    → Excel cell

Result: a fair test of the engine the bank actually uses, not of "how well
gemma handles a 60K-char document stuffed into one prompt."

Auth: Bearer API token created in RAGFlow UI (Profile → API → Create new key).

Output: same Excel template, in-place fill of cols F (תשובת המערכת),
H (האם הלינק מפנה לנוהל הנכון?), and J (verdict).

Usage:
    python tools/scripts/eval_excel_ragflow.py \\
        --xlsx C:/develop/html_output/_eval_report/newtest/test_report_24_05.xlsx \\
        --out  C:/develop/html_output/_eval_report/newtest/test_report_24_05_ragflow.xlsx \\
        --kb-name hozrim \\
        --token RAGFLOW_API_TOKEN_HERE
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import openpyxl

# UTF-8 stdout so Hebrew logs don't crash on Windows cp1252.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# Reuse the existing JSON-extraction + ollama-judge primitives. The judge runs
# locally against ollama (same model RAGFlow uses) — keeping it independent of
# RAGFlow itself so a wrong/empty RAGFlow answer can still be graded fairly.
from tools.scripts.eval_html_qa import (  # noqa: E402
    NUM_PREDICT_JUDGE,
    extract_json,
    ollama_generate,
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RAGFLOW_BASE_URL = os.environ.get("RAGFLOW_BASE_URL", "http://localhost:9380")
REQUEST_TIMEOUT_SEC = 600   # RAGFlow + retrieval + LLM can be slow on CPU.

# Excel layout (1-based for openpyxl).
COL_NOHEL = 2          # col B — מס' נוהל
COL_QUESTION = 5       # col E — שאלה
COL_MODEL_ANSWER = 6   # col F — תשובת המערכת (we fill this)
COL_GOLD_ANSWER = 7    # col G — תשובה נכונה
COL_LINK_OK = 8        # col H — האם הלינק מפנה לנוהל הנכון? (we fill this)
COL_VERDICT = 10       # col J — מענה תקין/חלקי/לא תקין (we fill this)
FIRST_DATA_ROW = 6     # 1-based: rows 1-4 are header/legend, row 5 is column titles


PROMPT_JUDGE_3CLASS = """אתה שופט תשובות עבור מערכת בנקאית. עליך לבדוק האם תשובת המודל **תקפה עניינית** עבור השאלה — לא להשוות מילולית לתשובת הזהב.

עקרונות חשובים:
1. תשובת הזהב היא **דוגמה אחת** לתשובה נכונה. ייתכנו תשובות נכונות אחרות.
2. אם תשובת המודל מבוססת על נוהל אחר אך עונה תוכנית על השאלה — היא תקפה.
3. אם תשובת המודל מנוסחת אחרת אבל המידע העיקרי **תואם עובדתית** לתשובת הזהב — היא תקפה.
4. תשובה חלקית שמכסה את עיקר השאלה היא "תקין", לא "חלקי". "חלקי" שמור לתשובה שחסר בה פרט מהותי שמשנה את המשמעות.
5. "לא תקין" שמור ל:
   - תשובה שגויה עובדתית (סותר את הזהב או את הנהלים)
   - תשובה לא רלוונטית (לא עונה על השאלה)
   - תשובה "המידע אינו קיים" כשיש לתשובה מקור ברור (לפי הזהב)
   - הזיה (תשובה מפורטת כשהזהב אומר "המידע אינו קיים")

החזר JSON תקני בלבד בצורה: {{"verdict": "תקין" | "חלקי" | "לא תקין", "reason": "סיבה קצרה אם חלקי או לא תקין"}}

שאלה: {q}
תשובת זהב (דוגמה): {gold}
תשובת המודל: {actual}
"""


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("eval_ragflow")


# ---------------------------------------------------------------------------
# RAGFlow REST client (no third-party SDK dep — urllib only for portability)
# ---------------------------------------------------------------------------

class RagflowClient:
    def __init__(self, base_url: str, token: str):
        self.base = base_url.rstrip("/")
        self.token = token

    def _request(self, method: str, path: str, body: dict | None = None,
                 params: dict | None = None, timeout: int = REQUEST_TIMEOUT_SEC) -> dict:
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            body_text = ""
            try:
                body_text = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            raise RuntimeError(f"RAGFlow {method} {path} failed: HTTP {e.code} — {body_text[:300]}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"RAGFlow {method} {path} failed: {e}") from e
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}

    # ---- helpers -----------------------------------------------------------

    @staticmethod
    def _unwrap_list(resp: dict) -> list[dict]:
        """RAGFlow returns one of three shapes depending on version + endpoint:
            {data: [...]}                       — datasets
            {data: {items: [...], total: N}}    — generic paged list
            {data: {chats: [...], total: N}}    — /chats specifically
        Pick the first list value we find inside data."""
        d = resp.get("data")
        if isinstance(d, list):
            return d
        if isinstance(d, dict):
            for key in ("items", "chats", "datasets", "documents", "sessions"):
                v = d.get(key)
                if isinstance(v, list):
                    return v
            # Fallback: any list-typed value.
            for v in d.values():
                if isinstance(v, list):
                    return v
        return []

    def find_dataset_by_name(self, name: str) -> dict | None:
        resp = self._request("GET", "/api/v1/datasets", params={"page": 1, "page_size": 100})
        for ds in self._unwrap_list(resp):
            if (ds.get("name") or "").lower() == name.lower():
                return ds
        return None

    def find_chat_by_name(self, name: str) -> dict | None:
        resp = self._request("GET", "/api/v1/chats", params={"page": 1, "page_size": 100})
        for c in self._unwrap_list(resp):
            if (c.get("name") or "").lower() == name.lower():
                return c
        return None

    def create_chat(self, name: str, dataset_id: str, llm_id: str | None = None) -> dict:
        """Create a new chat assistant tied to one dataset.

        We deliberately keep the prompt minimal — RAGFlow ships with a
        Hebrew-friendly default that includes the {knowledge} placeholder."""
        body: dict[str, Any] = {
            "name": name,
            "dataset_ids": [dataset_id],
        }
        if llm_id:
            body["llm"] = {"model_name": llm_id}
        resp = self._request("POST", "/api/v1/chats", body=body)
        if resp.get("code") not in (0, None):
            raise RuntimeError(f"create_chat failed: {resp}")
        return resp.get("data") or resp

    def ask_openai_compat(self, chat_id: str, question: str,
                          model: str | None = None) -> tuple[str, list[str]]:
        """Ask one question via RAGFlow's OpenAI-compatible endpoint.

        Returns (answer_text, cited_doc_names). RAGFlow embeds citations
        inline in the answer text as references like ``"טסט/40706.html"``."""
        import re
        body = {
            "model": model or "model",  # "model" placeholder = use chat's default LLM
            "messages": [{"role": "user", "content": question}],
            "stream": False,
        }
        resp = self._request(
            "POST", f"/api/v1/chats_openai/{chat_id}/chat/completions", body=body
        )
        if "choices" not in resp:
            raise RuntimeError(f"unexpected RAGFlow response: {str(resp)[:300]}")
        answer = resp["choices"][0]["message"]["content"] or ""
        cited = sorted(set(re.findall(r"\b(\d+)\.html\b", answer)))
        return answer.strip(), [f"{c}.html" for c in cited]


# ---------------------------------------------------------------------------
# Per-row evaluation
# ---------------------------------------------------------------------------

def evaluate_row(client: RagflowClient, chat_id: str, question: str, gold: str,
                 expected_nohel: str) -> tuple[str, str, str, str]:
    """Returns (model_answer, link_ok, verdict, reason).

    link_ok is "כן" / "לא" / "" depending on whether the references RAGFlow
    cited include the expected נוהל file. verdict is one of the three Hebrew
    labels (or "ERROR")."""
    # Step 1: ask through RAGFlow.
    try:
        answer, cited_doc_names = client.ask_openai_compat(chat_id, question)
    except Exception as e:
        return "", "", "ERROR", f"ragflow ask failed: {e}"

    if not answer:
        return "", "", "ERROR", "RAGFlow returned empty answer"

    # Step 2: check citations. cited_doc_names contains strings like
    # 'טסט/40706.html'. We accept a hit if any of them ends with
    # '<expected_nohel>.html'.
    expected_marker = f"{expected_nohel}.html"
    link_ok = (
        "כן" if any(n.endswith(expected_marker) for n in cited_doc_names)
        else "לא" if cited_doc_names
        else ""
    )

    # Step 3: judge the answer with local ollama (same model, but independent
    # of RAGFlow — keeps the verdict honest even when RAGFlow misfires).
    # Long RAGFlow answers (Markdown tables, multi-section explanations) push
    # gemma's thinking phase past the predict budget, leaving the visible JSON
    # truncated. Cap the answer text we send to the judge — its job is to
    # compare semantics, not to read the full essay.
    JUDGE_ANSWER_CAP = 2000
    answer_for_judge = answer if len(answer) <= JUDGE_ANSWER_CAP else (
        answer[:JUDGE_ANSWER_CAP] + "\n[... truncated ...]"
    )
    try:
        judge_raw = ollama_generate(
            PROMPT_JUDGE_3CLASS.format(q=question, gold=gold, actual=answer_for_judge),
            num_predict=NUM_PREDICT_JUDGE * 5,  # 4000 tokens for thinking + JSON output.
        )
        judge = extract_json(judge_raw)
        verdict = str(judge.get("verdict", "")).strip()
        reason = str(judge.get("reason", "")).strip()
        if verdict not in ("תקין", "חלקי", "לא תקין"):
            return answer, link_ok, "ERROR", f"unparseable verdict: {judge_raw[:120]!r}"
    except Exception as e:
        return answer, link_ok, "ERROR", f"judge failed: {e}"

    return answer, link_ok, verdict, reason


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--xlsx", required=True, type=Path, help="input Excel template")
    p.add_argument("--out", required=True, type=Path, help="output Excel path")
    p.add_argument("--kb-name", required=True, help="RAGFlow dataset name (e.g. hozrim)")
    p.add_argument("--token", required=True, help="RAGFlow API token (Profile → API → Create new key)")
    p.add_argument("--chat-name", default="bank-eval",
                   help="Chat assistant name. Reused if it already exists; created if not.")
    p.add_argument("--llm-id", default=None,
                   help="Optional LLM model id override (e.g. 'gemma4:26b@Ollama'). Uses the chat's default if omitted.")
    p.add_argument("--base-url", default=RAGFLOW_BASE_URL, help="RAGFlow base URL")
    p.add_argument("--limit", type=int, default=0, help="stop after N rows (0 = all)")
    p.add_argument("--start-row", type=int, default=FIRST_DATA_ROW,
                   help=f"1-based row to start from (default {FIRST_DATA_ROW}). Useful for resuming.")
    p.add_argument("--skip-filled", action="store_true",
                   help="skip rows that already have a model answer")
    p.add_argument("--rows", default=None,
                   help="Comma-separated 1-based Excel row numbers to process (e.g. '11,12,14'). "
                        "When set, the output file is read first and only those rows are touched.")
    args = p.parse_args()

    if not args.xlsx.is_file():
        log.error(f"missing xlsx: {args.xlsx}")
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)

    client = RagflowClient(args.base_url, args.token)

    # Resolve dataset.
    log.info(f"looking up dataset {args.kb_name!r}…")
    ds = client.find_dataset_by_name(args.kb_name)
    if not ds:
        log.error(f"dataset not found: {args.kb_name!r}. Available datasets via the API may be paginated.")
        return 2
    dataset_id = ds.get("id") or ds.get("dataset_id")
    log.info(f"  dataset id={dataset_id}, doc_num={ds.get('doc_num')}, chunk_num={ds.get('chunk_num')}")

    # Resolve or create chat assistant.
    log.info(f"looking up chat {args.chat_name!r}…")
    chat = client.find_chat_by_name(args.chat_name)
    if chat:
        chat_id = chat["id"]
        log.info(f"  reusing existing chat id={chat_id}")
    else:
        log.info(f"  creating chat {args.chat_name!r} bound to dataset {dataset_id}")
        chat = client.create_chat(args.chat_name, dataset_id, llm_id=args.llm_id)
        chat_id = chat["id"]
        log.info(f"  created chat id={chat_id}")

    # In --rows mode, edit the existing output file in-place so we don't
    # clobber rows that were already filled. Otherwise start fresh from the
    # template.
    rows_filter: set[int] | None = None
    if args.rows:
        rows_filter = {int(s.strip()) for s in args.rows.split(",") if s.strip()}
        source = args.out if args.out.is_file() else args.xlsx
        log.info(f"--rows mode: editing {source} for rows {sorted(rows_filter)}")
        wb = openpyxl.load_workbook(source)
    else:
        wb = openpyxl.load_workbook(args.xlsx)
    ws = wb.active
    for s in wb.worksheets:
        if hasattr(s, "_images"):
            s._images = []
    log.info(f"workbook: sheet={ws.title!r}, rows={ws.max_row}")

    counts = {"תקין": 0, "חלקי": 0, "לא תקין": 0, "ERROR": 0, "SKIPPED": 0}
    rows_processed = 0
    t0 = time.time()

    for row_idx in range(args.start_row, ws.max_row + 1):
        if rows_filter is not None and row_idx not in rows_filter:
            continue
        nohel = ws.cell(row=row_idx, column=COL_NOHEL).value
        question = ws.cell(row=row_idx, column=COL_QUESTION).value
        gold = ws.cell(row=row_idx, column=COL_GOLD_ANSWER).value
        existing = ws.cell(row=row_idx, column=COL_MODEL_ANSWER).value
        if not nohel or not question:
            continue
        if args.skip_filled and existing:
            counts["SKIPPED"] += 1
            continue

        nohel_str = str(nohel).strip()
        question_str = str(question).strip()
        gold_str = str(gold).strip() if gold else ""

        log.info(f"  row {row_idx} (נוהל={nohel_str}): {question_str[:60]}…")
        t_row = time.time()
        answer, link_ok, verdict, reason = evaluate_row(
            client, chat_id, question_str, gold_str, nohel_str
        )
        elapsed = time.time() - t_row

        ws.cell(row=row_idx, column=COL_MODEL_ANSWER).value = answer
        ws.cell(row=row_idx, column=COL_LINK_OK).value = link_ok
        if verdict in ("חלקי", "לא תקין") and reason:
            ws.cell(row=row_idx, column=COL_VERDICT).value = f"{verdict} — {reason}"
        else:
            ws.cell(row=row_idx, column=COL_VERDICT).value = verdict

        counts[verdict if verdict in counts else "ERROR"] += 1
        log.info(f"    → {verdict} (link={link_ok or '?'}, {elapsed:.1f}s)")
        wb.save(args.out)

        rows_processed += 1
        if args.limit > 0 and rows_processed >= args.limit:
            log.info(f"hit --limit={args.limit}, stopping")
            break

    total_time = time.time() - t0
    log.info("=" * 60)
    log.info(f"DONE in {total_time:.1f}s — {rows_processed} rows processed")
    for k, v in counts.items():
        log.info(f"  {k}: {v}")
    log.info(f"output: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

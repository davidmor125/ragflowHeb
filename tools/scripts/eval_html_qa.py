#!/usr/bin/env python3
"""HTML Q&A evaluation against a local Ollama model (default: gemma4:26b).

For each .html file in a directory:
  1. Extract clean text via the project's RAGFlowHtmlParser (so we test the
     same Hebrew-aware extraction path that the ingestion pipeline uses).
  2. Ask the LLM to generate N question + gold-answer pairs from that text.
  3. Ask the LLM each question (with the same text as context) and capture
     its answer.
  4. Ask the LLM to judge whether the answer matches the gold (LLM-as-judge).
  5. Write a UTF-8 Markdown report + a CSV summary.

UTF-8 EVERYWHERE: file reads, file writes, stdout, and the Ollama HTTP
payloads. On Windows the console is reconfigured to UTF-8 so we never hit
cp1252 encode errors on Hebrew output.

Usage:
    python tools/scripts/eval_html_qa.py \
        --html-dir C:/develop/html_output \
        --report-dir C:/develop/html_output/_eval_report

Defaults are tuned to gemma4:26b which has a long thinking phase
(~300 tokens) before producing visible output, so num_predict is set high.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

# UTF-8 console on Windows. Without this, print() of Hebrew dies under cp1252.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# Make the project importable so we can reuse RAGFlowHtmlParser, the same
# parser the production ingestion path uses for HTML.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from deepdoc.parser.html_parser import RAGFlowHtmlParser
except Exception:
    RAGFlowHtmlParser = None  # Fallback to BeautifulSoup-only extraction.

from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:26b")

# Gemma's thinking phase eats ~300 tokens before any visible output. We keep
# a generous budget so even a multi-question JSON reply has room.
NUM_PREDICT_GENERATE = 4000   # Q&A generation (longest output).
NUM_PREDICT_ANSWER = 1500     # Answering one question.
NUM_PREDICT_JUDGE = 800       # Yes/no judgement + brief reasoning.

# Hard cap on the document text we send to the model. gemma4:26b has a large
# context but we keep this conservative for speed; bump if your docs are big.
MAX_DOC_CHARS = 12000

REQUEST_TIMEOUT_SEC = 600     # gemma4:26b on CPU can be slow.

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("eval_html_qa")


# ---------------------------------------------------------------------------
# HTML extraction
# ---------------------------------------------------------------------------

def extract_text_from_html(path: Path) -> str:
    """Extract human-readable text from an HTML file as UTF-8.

    Prefer RAGFlowHtmlParser (project's own pipeline). Fall back to a plain
    BeautifulSoup extraction so this script keeps working even if the parser
    import fails (e.g. missing optional deps in this env)."""
    raw = path.read_bytes()
    if RAGFlowHtmlParser is not None:
        try:
            sections = RAGFlowHtmlParser()(str(path), binary=raw, chunk_token_num=512)
            text = "\n\n".join(s for s in sections if s and s.strip())
            if text.strip():
                return text
        except Exception as e:
            log.warning(f"RAGFlowHtmlParser failed on {path.name}: {e!r}; falling back to bs4")
    # Fallback path.
    try:
        html = raw.decode("utf-8")
    except UnicodeDecodeError:
        html = raw.decode("utf-8", errors="ignore")
    # html.parser is in the stdlib so this fallback works in any env, even
    # when html5lib (used by the project's RAGFlowHtmlParser) is missing.
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


# ---------------------------------------------------------------------------
# Ollama client
# ---------------------------------------------------------------------------

def ollama_generate(prompt: str, num_predict: int, temperature: float = 0.0) -> str:
    """Call Ollama /api/generate and return the response text. UTF-8 in/out."""
    body = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
        },
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
            payload = resp.read().decode("utf-8")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Ollama request failed: {e}") from e
    parsed = json.loads(payload)
    return parsed.get("response", "") or ""


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PROMPT_GENERATE_QA = """אתה עוזר שמייצר שאלות בדיקה למסמך.

קרא את הטקסט הבא בעיון. צור בדיוק {n} שאלות בעברית שניתן לענות עליהן ישירות מתוך הטקסט. לכל שאלה ספק את התשובה הקצרה והמדויקת ביותר שמופיעה במפורש בטקסט.

החזר את התוצאה בפורמט JSON תקני בלבד, ללא שום טקסט נוסף, בצורה הזו:
{{"qa": [{{"q": "שאלה 1", "a": "תשובה 1"}}, {{"q": "שאלה 2", "a": "תשובה 2"}}]}}

טקסט המסמך:
\"\"\"
{doc}
\"\"\"
"""

PROMPT_ANSWER = """ענה על השאלה הבאה אך ורק על סמך הטקסט שלהלן. אם התשובה לא מופיעה בטקסט, ענה: "לא נמצא בטקסט".

תן תשובה קצרה ותכליתית בעברית. אל תוסיף הסברים מיותרים.

טקסט:
\"\"\"
{doc}
\"\"\"

שאלה: {q}

תשובה:"""

PROMPT_JUDGE = """אתה שופט. בהינתן שאלה, תשובה רצויה (gold), ותשובה של מודל, החלט אם תשובת המודל נכונה מבחינה עובדתית ומשמעותית, גם אם הניסוח שונה.

החזר JSON תקני בלבד בצורה: {{"verdict": "PASS"}} או {{"verdict": "FAIL", "reason": "סיבה קצרה"}}

שאלה: {q}
תשובה רצויה: {gold}
תשובת המודל: {actual}
"""


# ---------------------------------------------------------------------------
# Robust JSON extraction (LLMs sometimes wrap JSON in prose / code fences)
# ---------------------------------------------------------------------------

def extract_json(text: str) -> Any:
    """Pull the first JSON object/array out of an LLM response.

    Tolerant to truncation: when the model's output gets cut off mid-JSON
    (a real failure mode with gemma4:26b on long Hebrew Q&A generation),
    we fall back to extracting whatever complete ``{"q":..., "a":...}``
    pairs we can find inside the partial text. Better to return 3 valid
    pairs than to abort the entire file."""
    text = text.strip()
    # Strip code fences if present.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]

    # Strict path: find first balanced { or [ and parse cleanly.
    for opener, closer in [("{", "}"), ("[", "]")]:
        start = text.find(opener)
        if start == -1:
            continue
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
                continue
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break

    # Lenient path: scrape complete {"q": "...", "a": "..."} objects from a
    # truncated stream. Each q/a object is balanced on its own braces, so
    # we can recover them even when the enclosing array/object never closed.
    # Skip past unclosed outer objects rather than aborting at the first
    # unbalanced brace (the outer envelope is exactly what's truncated).
    qa_items: list[dict] = []
    i = 0
    while i < len(text):
        if text[i] != "{":
            i += 1
            continue
        depth = 0
        in_str = False
        escape = False
        end = -1
        for j in range(i, len(text)):
            ch = text[j]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        if end == -1:
            # This brace never closed; advance one char and keep looking
            # for inner {q,a} objects that may be complete.
            i += 1
            continue
        candidate = text[i : end + 1]
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict) and "q" in obj and "a" in obj:
                qa_items.append(obj)
        except json.JSONDecodeError:
            pass
        i = end + 1

    if qa_items:
        return {"qa": qa_items}

    raise ValueError(f"No JSON found in LLM response: {text[:200]!r}")


# ---------------------------------------------------------------------------
# Per-file evaluation
# ---------------------------------------------------------------------------

@dataclass
class QAResult:
    question: str
    gold_answer: str
    model_answer: str
    verdict: str  # "PASS" | "FAIL" | "ERROR"
    reason: str = ""


@dataclass
class FileResult:
    file: str
    char_count: int
    qa_count: int
    pass_count: int
    fail_count: int
    error_count: int
    items: list[QAResult] = field(default_factory=list)
    error: str = ""

    @property
    def pass_rate(self) -> float:
        if self.qa_count == 0:
            return 0.0
        return self.pass_count / self.qa_count


def truncate_doc(text: str, limit: int = MAX_DOC_CHARS) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + "\n[...truncated...]\n" + text[-half:]


def evaluate_file(path: Path, n_questions: int) -> FileResult:
    log.info(f"--- {path.name} ---")
    try:
        full_text = extract_text_from_html(path)
    except Exception as e:
        log.exception(f"extract failed: {path.name}")
        return FileResult(file=path.name, char_count=0, qa_count=0,
                          pass_count=0, fail_count=0, error_count=0,
                          error=f"extract: {e}")
    char_count = len(full_text)
    if char_count < 50:
        log.warning(f"text too short ({char_count} chars), skipping")
        return FileResult(file=path.name, char_count=char_count, qa_count=0,
                          pass_count=0, fail_count=0, error_count=0,
                          error="text too short")

    doc_for_prompt = truncate_doc(full_text)

    # 1. Generate Q&A pairs.
    log.info(f"  generating {n_questions} Q&A pairs (chars={char_count})")
    try:
        gen_resp = ollama_generate(
            PROMPT_GENERATE_QA.format(n=n_questions, doc=doc_for_prompt),
            num_predict=NUM_PREDICT_GENERATE,
        )
        parsed = extract_json(gen_resp)
        qa_pairs = parsed.get("qa") if isinstance(parsed, dict) else parsed
        if not isinstance(qa_pairs, list) or not qa_pairs:
            raise ValueError(f"no qa list in: {gen_resp[:300]!r}")
    except Exception as e:
        log.exception(f"Q&A generation failed: {path.name}")
        return FileResult(file=path.name, char_count=char_count, qa_count=0,
                          pass_count=0, fail_count=0, error_count=0,
                          error=f"qa-gen: {e}")

    # 2. Ask each question; 3. Judge.
    items: list[QAResult] = []
    for idx, pair in enumerate(qa_pairs[:n_questions], 1):
        q = (pair.get("q") or "").strip()
        gold = (pair.get("a") or "").strip()
        if not q or not gold:
            items.append(QAResult(q, gold, "", "ERROR", "empty q or gold"))
            continue
        log.info(f"  Q{idx}: {q[:80]}")
        try:
            answer = ollama_generate(
                PROMPT_ANSWER.format(doc=doc_for_prompt, q=q),
                num_predict=NUM_PREDICT_ANSWER,
            ).strip()
        except Exception as e:
            items.append(QAResult(q, gold, "", "ERROR", f"answer: {e}"))
            continue
        try:
            judge_raw = ollama_generate(
                PROMPT_JUDGE.format(q=q, gold=gold, actual=answer),
                num_predict=NUM_PREDICT_JUDGE,
            )
            judge = extract_json(judge_raw)
            verdict = str(judge.get("verdict", "")).upper()
            reason = str(judge.get("reason", "")) if verdict == "FAIL" else ""
            if verdict not in ("PASS", "FAIL"):
                verdict = "ERROR"
                reason = f"unparseable verdict: {judge_raw[:200]!r}"
        except Exception as e:
            verdict, reason = "ERROR", f"judge: {e}"
        items.append(QAResult(q, gold, answer, verdict, reason))
        log.info(f"    -> {verdict}")

    pc = sum(1 for r in items if r.verdict == "PASS")
    fc = sum(1 for r in items if r.verdict == "FAIL")
    ec = sum(1 for r in items if r.verdict == "ERROR")
    return FileResult(
        file=path.name,
        char_count=char_count,
        qa_count=len(items),
        pass_count=pc,
        fail_count=fc,
        error_count=ec,
        items=items,
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def write_markdown_report(results: list[FileResult], out: Path) -> None:
    lines: list[str] = []
    total_qa = sum(r.qa_count for r in results)
    total_pass = sum(r.pass_count for r in results)
    total_fail = sum(r.fail_count for r in results)
    total_err = sum(r.error_count for r in results)
    overall_rate = (total_pass / total_qa * 100) if total_qa else 0.0

    lines.append(f"# HTML Q&A Evaluation — {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append(f"- **Model**: `{OLLAMA_MODEL}` via `{OLLAMA_URL}`")
    lines.append(f"- **Files evaluated**: {len(results)}")
    lines.append(f"- **Total Q&A**: {total_qa}")
    lines.append(f"- **PASS**: {total_pass} ({overall_rate:.1f}%)")
    lines.append(f"- **FAIL**: {total_fail}")
    lines.append(f"- **ERROR**: {total_err}")
    lines.append("")
    lines.append("## Per-file summary")
    lines.append("")
    lines.append("| File | Chars | Q&A | PASS | FAIL | ERR | Rate |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for r in results:
        rate = f"{r.pass_rate*100:.0f}%" if r.qa_count else "—"
        lines.append(f"| {r.file} | {r.char_count} | {r.qa_count} | {r.pass_count} | {r.fail_count} | {r.error_count} | {rate} |")

    lines.append("")
    lines.append("## Details")
    for r in results:
        lines.append("")
        lines.append(f"### {r.file}")
        if r.error:
            lines.append(f"> ERROR: {r.error}")
            continue
        for i, it in enumerate(r.items, 1):
            badge = {"PASS": "✅", "FAIL": "❌", "ERROR": "⚠️"}.get(it.verdict, "?")
            lines.append("")
            lines.append(f"**Q{i} {badge} {it.verdict}**")
            lines.append(f"- שאלה: {it.question}")
            lines.append(f"- תשובה נכונה: {it.gold_answer}")
            lines.append(f"- תשובת המודל: {it.model_answer}")
            if it.reason:
                lines.append(f"- סיבה לכישלון: {it.reason}")
    out.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"wrote markdown report: {out}")


def write_csv_report(results: list[FileResult], out: Path) -> None:
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        # utf-8-sig adds a BOM so Excel on Windows shows Hebrew correctly.
        w = csv.writer(f)
        w.writerow(["file", "q_index", "question", "gold_answer", "model_answer", "verdict", "reason"])
        for r in results:
            if r.error:
                w.writerow([r.file, "", "", "", "", "FILE_ERROR", r.error])
                continue
            for i, it in enumerate(r.items, 1):
                w.writerow([r.file, i, it.question, it.gold_answer, it.model_answer, it.verdict, it.reason])
    log.info(f"wrote CSV report: {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--html-dir", required=True, type=Path)
    p.add_argument("--report-dir", required=True, type=Path)
    p.add_argument("--n-questions", type=int, default=5)
    p.add_argument("--limit", type=int, default=0,
                   help="Stop after N files (0 = no limit). Useful for smoke tests.")
    p.add_argument("--only", default=None,
                   help="Comma-separated list of filenames to process; everything else is skipped. "
                        "Useful for reruns. Combined with --merge, results overwrite the prior entry "
                        "for each named file in the existing report.")
    p.add_argument("--merge", action="store_true",
                   help="Merge new results into existing report.json in --report-dir, replacing any "
                        "prior entries for files that get rerun. Without this flag, the report is "
                        "rewritten from scratch.")
    p.add_argument("--model", default=None,
                   help="Override OLLAMA_MODEL env var")
    args = p.parse_args()

    if args.model:
        global OLLAMA_MODEL
        OLLAMA_MODEL = args.model

    if not args.html_dir.is_dir():
        log.error(f"not a directory: {args.html_dir}")
        return 2
    args.report_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(args.html_dir.glob("*.html"))
    if not files:
        log.error(f"no .html files in {args.html_dir}")
        return 2
    if args.only:
        wanted = {name.strip() for name in args.only.split(",") if name.strip()}
        files = [f for f in files if f.name in wanted]
        missing = wanted - {f.name for f in files}
        if missing:
            log.warning(f"--only: not found in {args.html_dir}: {sorted(missing)}")
        if not files:
            log.error("--only filtered out all files; nothing to do")
            return 2
    if args.limit > 0:
        files = files[: args.limit]
    log.info(f"evaluating {len(files)} files with {OLLAMA_MODEL}")

    # Load prior report so merge mode can preserve already-good entries.
    prior_by_name: dict[str, FileResult] = {}
    if args.merge:
        prior_path = args.report_dir / "report.json"
        if prior_path.exists():
            try:
                raw = json.loads(prior_path.read_text(encoding="utf-8"))
                for entry in raw:
                    items = [QAResult(**it) for it in entry.get("items", [])]
                    fr = FileResult(
                        file=entry["file"],
                        char_count=entry.get("char_count", 0),
                        qa_count=entry.get("qa_count", 0),
                        pass_count=entry.get("pass_count", 0),
                        fail_count=entry.get("fail_count", 0),
                        error_count=entry.get("error_count", 0),
                        items=items,
                        error=entry.get("error", ""),
                    )
                    prior_by_name[fr.file] = fr
                log.info(f"loaded {len(prior_by_name)} prior entries from {prior_path}")
            except Exception as e:
                log.warning(f"could not load prior report (will start fresh): {e}")

    results: list[FileResult] = []
    t0 = time.time()
    for path in files:
        t_file = time.time()
        try:
            result = evaluate_file(path, args.n_questions)
        except Exception as e:
            log.exception(f"unexpected failure on {path.name}")
            result = FileResult(file=path.name, char_count=0, qa_count=0,
                                pass_count=0, fail_count=0, error_count=0,
                                error=f"unexpected: {e}")
        results.append(result)
        log.info(f"  {path.name}: PASS={result.pass_count}/{result.qa_count} "
                 f"FAIL={result.fail_count} ERR={result.error_count} "
                 f"({time.time()-t_file:.1f}s)")
        # Incremental save so a long run never loses progress. In merge mode
        # we splice the new entry over any prior entry for the same file,
        # preserving the order of the original report.
        if args.merge and prior_by_name:
            merged = dict(prior_by_name)  # copy
            for r in results:
                merged[r.file] = r
            to_write = sorted(merged.values(), key=lambda r: r.file)
        else:
            to_write = results
        write_markdown_report(to_write, args.report_dir / "report.md")
        write_csv_report(to_write, args.report_dir / "report.csv")
        (args.report_dir / "report.json").write_text(
            json.dumps([asdict(r) for r in to_write], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    log.info(f"done in {time.time()-t0:.1f}s")
    log.info(f"report dir: {args.report_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

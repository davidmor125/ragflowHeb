#!/usr/bin/env python3
"""Re-run only the LLM judge on items previously marked verdict=ERROR.

The original eval gave the judge a 800-token budget, which was sometimes
eaten entirely by Gemma's thinking phase, leaving an empty visible response
and an unparseable verdict. We bump the budget here and splice the new
verdicts back into report.json, then regenerate the markdown / csv reports.

Usage:
    python tools/scripts/rejudge_errors.py \\
        --report-dir C:/develop/html_output/_eval_report
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# UTF-8 console on Windows.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Reuse the eval script's primitives.
sys.path.insert(0, str(Path(__file__).parent))
from eval_html_qa import (
    PROMPT_JUDGE,
    QAResult,
    FileResult,
    extract_json,
    ollama_generate,
    write_csv_report,
    write_markdown_report,
)

REJUDGE_NUM_PREDICT = 1800  # vs. 800 in the original run; thinking eats ~300.

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("rejudge")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report-dir", required=True, type=Path)
    args = p.parse_args()

    rep_path = args.report_dir / "report.json"
    raw = json.loads(rep_path.read_text(encoding="utf-8"))

    # Find ERROR items.
    error_locations: list[tuple[int, int]] = []
    for fi, entry in enumerate(raw):
        for qi, item in enumerate(entry.get("items", [])):
            if item.get("verdict") == "ERROR":
                error_locations.append((fi, qi))

    log.info(f"found {len(error_locations)} ERROR items to re-judge")
    if not error_locations:
        log.info("nothing to do")
        return 0

    # Re-judge each.
    for fi, qi in error_locations:
        entry = raw[fi]
        item = entry["items"][qi]
        q = item.get("question", "")
        gold = item.get("gold_answer", "")
        actual = item.get("model_answer", "")
        log.info(f"  {entry['file']} Q{qi+1}: re-judging")
        if not actual:
            log.warning("    model_answer is empty; cannot re-judge")
            continue
        try:
            judge_raw = ollama_generate(
                PROMPT_JUDGE.format(q=q, gold=gold, actual=actual),
                num_predict=REJUDGE_NUM_PREDICT,
            )
            judge = extract_json(judge_raw)
            verdict = str(judge.get("verdict", "")).upper()
            reason = str(judge.get("reason", "")) if verdict == "FAIL" else ""
            if verdict not in ("PASS", "FAIL"):
                log.warning(f"    still unparseable: {judge_raw[:120]!r}")
                continue
        except Exception as e:
            log.warning(f"    judge failed again: {e}")
            continue
        item["verdict"] = verdict
        item["reason"] = reason
        log.info(f"    -> {verdict}")

    # Recompute counts per file.
    for entry in raw:
        items = entry.get("items", [])
        entry["pass_count"] = sum(1 for it in items if it.get("verdict") == "PASS")
        entry["fail_count"] = sum(1 for it in items if it.get("verdict") == "FAIL")
        entry["error_count"] = sum(1 for it in items if it.get("verdict") == "ERROR")

    # Save updated JSON and regenerate human-readable reports.
    rep_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"updated {rep_path}")

    # Reconstitute FileResult objects so we can reuse the same writers.
    file_results: list[FileResult] = []
    for entry in raw:
        items = [QAResult(**it) for it in entry.get("items", [])]
        file_results.append(FileResult(
            file=entry["file"],
            char_count=entry.get("char_count", 0),
            qa_count=entry.get("qa_count", 0),
            pass_count=entry.get("pass_count", 0),
            fail_count=entry.get("fail_count", 0),
            error_count=entry.get("error_count", 0),
            items=items,
            error=entry.get("error", ""),
        ))
    write_markdown_report(file_results, args.report_dir / "report.md")
    write_csv_report(file_results, args.report_dir / "report.csv")
    log.info("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

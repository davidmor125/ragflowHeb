#!/usr/bin/env python3
"""Re-run answer + judge for items where the original answer came back empty.

When gemma4:26b's thinking phase consumes the entire NUM_PREDICT budget,
the visible response is "" and the verdict gets stamped ERROR. This script
re-asks just those questions with a larger answer budget, re-judges, and
splices the new verdicts back into report.json (then regenerates md/csv).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent))
from eval_html_qa import (
    PROMPT_ANSWER,
    PROMPT_JUDGE,
    QAResult,
    FileResult,
    extract_json,
    extract_text_from_html,
    ollama_generate,
    truncate_doc,
    write_csv_report,
    write_markdown_report,
)

REANSWER_NUM_PREDICT = 3000
REJUDGE_NUM_PREDICT = 1800

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("reanswer")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report-dir", required=True, type=Path)
    p.add_argument("--html-dir", required=True, type=Path)
    args = p.parse_args()

    rep_path = args.report_dir / "report.json"
    raw = json.loads(rep_path.read_text(encoding="utf-8"))

    # Find ERROR items with empty model_answer (the ones rejudge couldn't fix).
    targets: list[tuple[int, int]] = []
    for fi, entry in enumerate(raw):
        for qi, item in enumerate(entry.get("items", [])):
            if item.get("verdict") == "ERROR" and not item.get("model_answer"):
                targets.append((fi, qi))

    log.info(f"found {len(targets)} ERROR items with empty answers")
    if not targets:
        return 0

    # Cache extracted text per file (multiple errors in same file = 1 extract).
    text_cache: dict[str, str] = {}

    for fi, qi in targets:
        entry = raw[fi]
        item = entry["items"][qi]
        fname = entry["file"]
        q = item.get("question", "")
        gold = item.get("gold_answer", "")
        log.info(f"  {fname} Q{qi+1}: re-answering")

        if fname not in text_cache:
            try:
                text_cache[fname] = extract_text_from_html(args.html_dir / fname)
            except Exception as e:
                log.warning(f"    extract failed: {e}")
                continue
        doc = truncate_doc(text_cache[fname])

        try:
            answer = ollama_generate(
                PROMPT_ANSWER.format(doc=doc, q=q),
                num_predict=REANSWER_NUM_PREDICT,
            ).strip()
        except Exception as e:
            log.warning(f"    answer call failed: {e}")
            continue

        if not answer:
            log.warning("    still empty after re-answer; giving up on this item")
            continue

        log.info(f"    got answer ({len(answer)} chars), judging")
        try:
            judge_raw = ollama_generate(
                PROMPT_JUDGE.format(q=q, gold=gold, actual=answer),
                num_predict=REJUDGE_NUM_PREDICT,
            )
            judge = extract_json(judge_raw)
            verdict = str(judge.get("verdict", "")).upper()
            reason = str(judge.get("reason", "")) if verdict == "FAIL" else ""
            if verdict not in ("PASS", "FAIL"):
                log.warning(f"    unparseable verdict: {judge_raw[:120]!r}")
                continue
        except Exception as e:
            log.warning(f"    judge failed: {e}")
            continue

        item["model_answer"] = answer
        item["verdict"] = verdict
        item["reason"] = reason
        log.info(f"    -> {verdict}")

    # Recompute counts.
    for entry in raw:
        items = entry.get("items", [])
        entry["pass_count"] = sum(1 for it in items if it.get("verdict") == "PASS")
        entry["fail_count"] = sum(1 for it in items if it.get("verdict") == "FAIL")
        entry["error_count"] = sum(1 for it in items if it.get("verdict") == "ERROR")

    rep_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"updated {rep_path}")

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

"""Comprehensive audit of Hebrew chunking quality across multiple docs in hozrim KB.

Checks:
  1. Hebrew presence and direction
  2. Sentence fragmentation (chunks ending mid-word/mid-sentence)
  3. Table preservation (whether HTML tables survived as coherent chunks)
  4. Niqqud / encoding issues
  5. Numbered list integrity
"""

import sys
import json
import re
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

T = "ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI"
KB_ID = "dc0091ca46e211f196f633ac796a3d7a"
HTML_DIR = Path(r"C:/develop/html_output/_eval_report/newtest/טסט")

SAMPLE_FILES = ["20071.html", "32328.html", "20064.html", "12917.html", "34320.html"]

HEBREW_RE = re.compile(r"[֐-׿]")
NIQQUD_RE = re.compile(r"[֑-ׇ]")


def get(path):
    req = urllib.request.Request(
        f"http://localhost:9380{path}",
        headers={"Authorization": f"Bearer {T}"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))


def looks_truncated(text: str) -> str | None:
    """Return reason string if chunk looks broken at boundaries."""
    if not text:
        return "empty"
    text = text.strip()
    last = text[-1]
    # Bad endings: mid-sentence (no terminal punctuation) and very short last word
    last_word = text.split()[-1] if text.split() else ""
    if last not in ".!?:;\"')]}…׃" and len(last_word) <= 3 and HEBREW_RE.search(last_word):
        return f"ends mid-word: ...{text[-40:]!r}"
    if last not in ".!?:;\"')]}…׃" and not text.endswith(" "):
        return f"no terminal punct: ...{text[-40:]!r}"
    return None


def looks_truncated_start(text: str) -> str | None:
    """Bad start: starts mid-sentence."""
    text = text.strip()
    if not text:
        return None
    first_word = text.split()[0] if text.split() else ""
    # Starts with a lowercase Hebrew letter that isn't typical sentence start? Hebrew has no case
    # so we use a different heuristic: starts with subsection number like "1.36.6" mid-list
    if re.match(r"^\d+\.\d+\.\d+", first_word):
        return f"starts mid-subsection: {first_word!r}"
    # Or starts with conjunction
    if first_word in ("ו", "אבל", "אך", "אם", "כי", "אז"):
        return f"starts with conjunction: {first_word!r}"
    return None


def has_table(text: str) -> bool:
    return "<table" in text.lower() or "</tr>" in text.lower() or "│" in text or "| " in text


# Find doc IDs by name
docs_resp = get(f"/api/v1/datasets/{KB_ID}/documents?page=1&page_size=1000")
docs_raw = docs_resp.get("data", {})
docs = docs_raw.get("docs") if isinstance(docs_raw, dict) else docs_raw
if not docs and isinstance(docs_raw, dict):
    docs = docs_raw.get("items", [])

doc_ids = {}
for d in docs:
    if isinstance(d, dict):
        for sample in SAMPLE_FILES:
            if d.get("name", "").endswith(sample):
                doc_ids[sample] = d.get("id")
                break

print("=" * 70)
print("HEBREW CHUNKING AUDIT — hozrim KB")
print("=" * 70)

global_stats = {
    "total_chunks": 0,
    "trunc_end": 0,
    "trunc_start": 0,
    "tables": 0,
    "niqqud": 0,
    "no_hebrew": 0,
}

for fname, doc_id in doc_ids.items():
    if not doc_id:
        print(f"\n[{fname}] not found")
        continue
    print(f"\n{'─' * 70}")
    print(f"FILE: טסט/{fname}  (doc_id={doc_id[:16]})")
    print(f"{'─' * 70}")
    raw_path = HTML_DIR / fname
    raw_size = raw_path.stat().st_size if raw_path.exists() else 0
    print(f"  raw HTML size: {raw_size} bytes")

    chunks_resp = get(f"/api/v1/datasets/{KB_ID}/documents/{doc_id}/chunks?page=1&page_size=200")
    cd = chunks_resp.get("data", {})
    chunk_list = cd.get("chunks") if isinstance(cd, dict) else cd
    if not chunk_list and isinstance(cd, dict):
        chunk_list = cd.get("items", [])
    print(f"  chunks total: {len(chunk_list)}")

    file_stats = {"trunc_end": 0, "trunc_start": 0, "tables": 0, "niqqud": 0, "no_hebrew": 0}
    examples_end = []
    examples_start = []

    for c in chunk_list:
        if not isinstance(c, dict):
            continue
        content = c.get("content") or c.get("content_with_weight") or c.get("text", "")
        global_stats["total_chunks"] += 1
        if not HEBREW_RE.search(content):
            file_stats["no_hebrew"] += 1
            global_stats["no_hebrew"] += 1
        if NIQQUD_RE.search(content):
            file_stats["niqqud"] += 1
            global_stats["niqqud"] += 1
        if has_table(content):
            file_stats["tables"] += 1
            global_stats["tables"] += 1
        end_problem = looks_truncated(content)
        if end_problem:
            file_stats["trunc_end"] += 1
            global_stats["trunc_end"] += 1
            if len(examples_end) < 2:
                examples_end.append(end_problem)
        start_problem = looks_truncated_start(content)
        if start_problem:
            file_stats["trunc_start"] += 1
            global_stats["trunc_start"] += 1
            if len(examples_start) < 2:
                examples_start.append(start_problem)

    print(f"  chunks ending broken (mid-sentence/word):  {file_stats['trunc_end']}/{len(chunk_list)}")
    print(f"  chunks starting broken (mid-subsection):    {file_stats['trunc_start']}/{len(chunk_list)}")
    print(f"  chunks containing tables:                   {file_stats['tables']}")
    print(f"  chunks with niqqud:                         {file_stats['niqqud']}")
    print(f"  chunks with NO Hebrew at all:               {file_stats['no_hebrew']}")
    if examples_end:
        print(f"  example bad endings:")
        for ex in examples_end:
            print(f"    - {ex}")
    if examples_start:
        print(f"  example bad starts:")
        for ex in examples_start:
            print(f"    - {ex}")

print("\n" + "=" * 70)
print("AGGREGATE")
print("=" * 70)
total = global_stats["total_chunks"]
print(f"  total chunks across {len(doc_ids)} files:   {total}")
if total:
    print(f"  ending broken:                          {global_stats['trunc_end']} ({100*global_stats['trunc_end']/total:.0f}%)")
    print(f"  starting broken:                        {global_stats['trunc_start']} ({100*global_stats['trunc_start']/total:.0f}%)")
    print(f"  with tables:                            {global_stats['tables']}")
    print(f"  with niqqud:                            {global_stats['niqqud']}")
    print(f"  no Hebrew at all:                       {global_stats['no_hebrew']}")

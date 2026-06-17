"""For each of the 10 questions, capture:
  1. The chunks RAGFlow retrieves (with rerank scores)
  2. Whether the gold answer phrase appears in any of those chunks
  3. The actual answer gemma4 produced
  4. Diagnosis: was it a retrieval miss or an LLM miss?

This tells us where to focus next: chunking, retrieval, or LLM."""

import sys, json, urllib.request, re
import openpyxl
sys.stdout.reconfigure(encoding="utf-8")

T = "ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI"
KB_SMALL = "055ff3d2478b11f180e77faa71318e24"
CHAT_ID = "a7e5d00e478b11f180e77faa71318e24"

# Load the 10 questions and gold answers
wb = openpyxl.load_workbook(
    r"C:/develop/html_output/_eval_report/newtest/test_report_24_05.xlsx",
    read_only=True, data_only=True,
)
ws = wb.active
rows = list(ws.iter_rows(values_only=True))
questions = []
for r in rows[5:]:
    nohel, q, gold = r[1], r[4], r[6]
    if nohel and q:
        questions.append((str(nohel).strip(), str(q).strip(), str(gold or "").strip()))
        if len(questions) >= 10:
            break

# Load gemma4 answers from the latest run
ans_wb = openpyxl.load_workbook(
    r"C:/develop/html_output/_eval_report/newtest/test_report_24_05_ragflow_clean.xlsx",
    read_only=True, data_only=True,
)
ans_ws = ans_wb.active
gemma_answers = {}
for r in range(6, 16):
    nohel = ans_ws.cell(row=r, column=2).value
    q = ans_ws.cell(row=r, column=5).value
    a = ans_ws.cell(row=r, column=6).value
    v = ans_ws.cell(row=r, column=10).value
    if nohel and q:
        gemma_answers[str(q).strip()] = (str(a or ""), str(v or ""))


def post(path, body):
    req = urllib.request.Request(
        f"http://localhost:9380{path}",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {T}",
                 "Content-Type": "application/json; charset=utf-8"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=180).read().decode("utf-8"))


def gold_in_chunks(gold: str, chunks: list, top_n: int = 12) -> tuple[bool, int, int]:
    """Returns (found_in_top_n, rank_of_first_match, hits_in_best)"""
    common = {"של", "על", "את", "אם", "כי", "אינו", "אינה", "המידע", "הוא", "היא"}
    gold_words = [w for w in gold.split() if len(w) >= 4 and w not in common][:5]
    if not gold_words:
        return True, 0, 0  # gold answer like "המידע אינו קיים" — trivially true
    best_hits = 0
    rank = -1
    for i, c in enumerate(chunks[:top_n]):
        if not isinstance(c, dict):
            continue
        content = c.get("content", "")
        hits = sum(1 for w in gold_words if w in content)
        if hits >= 2 and rank == -1:
            rank = i + 1
        best_hits = max(best_hits, hits)
    return rank > 0, rank, best_hits


print("AUDIT: chunks delivered to gemma4 + answer outcome\n")
summary = {"rag_miss": 0, "llm_miss": 0, "ok": 0, "judge_lenient": 0}

for nohel, q, gold in questions:
    print("=" * 80)
    print(f"נוהל={nohel}: {q[:75]}")
    print(f"GOLD: {gold[:100]}")

    # Get top-12 chunks (matching what LLM sees)
    resp = post("/api/v1/retrieval", {
        "dataset_ids": [KB_SMALL],
        "question": q,
        "top_k": 12,
        "similarity_threshold": 0.1,
    })
    chunks = resp.get("data", {}).get("chunks", [])
    print(f"  RAGFlow returned {len(chunks)} chunks (top_n=12)")

    found, rank, hits = gold_in_chunks(gold, chunks, top_n=12)
    if found:
        print(f"  ✓ gold-answer terms IN TOP {rank}, best chunk has {hits} matching words")
    else:
        print(f"  ✗ gold-answer terms NOT IN TOP-12 (best: {hits} matching words)")

    # Show top 5 chunks briefly
    for i, c in enumerate(chunks[:5]):
        if not isinstance(c, dict): continue
        sim = c.get("similarity", 0)
        doc = c.get("document_keyword", "?").replace("טסט/", "").replace("to_upload_part1/", "").replace("to_upload_part2/", "")
        snippet = re.sub(r"\s+", " ", c.get("content", ""))[:80]
        print(f"    [{i+1}] sim={sim:.3f}  {doc[:18]:18s}  {snippet}")

    # gemma4 answer
    ans, verdict = gemma_answers.get(q, ("", ""))
    print(f"\n  gemma4 said: {ans[:200]}")
    print(f"  judge: {verdict[:100]}")

    # Classify
    if verdict.startswith("תקין"):
        summary["ok"] += 1
    elif "המידע אינו קיים" in (ans or ""):
        if found:
            summary["llm_miss"] += 1  # gold was there, LLM refused
            print("  >>> CLASSIFICATION: LLM REFUSED despite having gold")
        else:
            summary["rag_miss"] += 1
            print("  >>> CLASSIFICATION: RAG MISS - gold not retrieved")
    elif verdict.startswith("חלקי"):
        if found:
            summary["judge_lenient"] += 1  # answer ok but judge wants more
            print("  >>> CLASSIFICATION: PARTIAL — gold in context, gemma extracted some")
        else:
            summary["rag_miss"] += 1
    elif verdict.startswith("לא תקין"):
        if found:
            summary["llm_miss"] += 1
        else:
            summary["rag_miss"] += 1
    print()

print("=" * 80)
print(f"SUMMARY: {summary}")

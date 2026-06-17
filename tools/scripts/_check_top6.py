"""For each failing question, check what's actually in top-6 chunks (what
the LLM really sees) and whether the gold answer is in those 6.

This is critical: my earlier audit looked at top-30 but the chat is
configured with top_n=6, so the LLM only sees 6 chunks per question."""

import sys, json, urllib.request
import openpyxl
sys.stdout.reconfigure(encoding="utf-8")

T = "ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI"
KB_SMALL = "055ff3d2478b11f180e77faa71318e24"

wb = openpyxl.load_workbook(
    r"C:/develop/html_output/_eval_report/newtest/test_report_24_05_ragflow_clean.xlsx",
    read_only=True, data_only=True,
)
ws = wb.active

failing_rows = []
for r in range(6, 16):
    nohel = ws.cell(row=r, column=2).value
    q = ws.cell(row=r, column=5).value
    gold = ws.cell(row=r, column=7).value
    verdict = str(ws.cell(row=r, column=10).value or "")
    if nohel and q and verdict.startswith("לא תקין"):
        failing_rows.append((r, str(nohel), str(q), str(gold or "")))


def post(path, body):
    req = urllib.request.Request(
        f"http://localhost:9380{path}",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {T}",
                 "Content-Type": "application/json; charset=utf-8"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=180).read().decode("utf-8"))


print(f"Checking what top-6 (LLM-visible) chunks look like for {len(failing_rows)} failing rows\n")

for row_idx, nohel, q, gold in failing_rows:
    print("=" * 80)
    print(f"ROW {row_idx} (נוהל={nohel})")
    print(f"Q: {q[:80]}")
    print(f"GOLD: {gold[:120]}")

    # Get exactly 6 chunks (matches top_n=6)
    resp = post("/api/v1/retrieval", {
        "dataset_ids": [KB_SMALL],
        "question": q.strip(),
        "top_k": 6,
        "similarity_threshold": 0.1,
    })
    chunks = resp.get("data", {}).get("chunks", [])
    print(f"  LLM sees {len(chunks)} chunks (top_n=6, threshold=0.1)")

    common = {"של", "על", "את", "אם", "כי", "אינו", "אינה", "המידע", "הוא", "היא"}
    gold_words = [w for w in gold.split() if len(w) >= 4 and w not in common][:5]

    found_in_top_6 = False
    best_hits_in_top_6 = 0
    for i, c in enumerate(chunks):
        if not isinstance(c, dict):
            continue
        content = c.get("content", "")
        sim = c.get("similarity", 0)
        doc = c.get("document_keyword", "?").replace("טסט/", "")
        hits = sum(1 for w in gold_words if w in content)
        best_hits_in_top_6 = max(best_hits_in_top_6, hits)
        marker = ""
        if hits >= 2:
            marker = f"  ★★ {hits}/{len(gold_words)} gold words"
            found_in_top_6 = True
        elif hits == 1:
            marker = f"  ★ 1 gold word"
        print(f"    [{i+1}] sim={sim:.3f}  {doc[:30]:30s}{marker}")

    if not found_in_top_6:
        print(f"  >>> ⚠️  GOLD ANSWER NOT IN TOP-6 (best hits: {best_hits_in_top_6}/{len(gold_words)})")
    else:
        print(f"  >>> gold-answer-content IN TOP 6: YES")
    print()

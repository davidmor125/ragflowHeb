"""For each failing question, run RAGFlow's retrieval and check:
  1. Top-K chunks + their similarity score
  2. Whether the gold answer text actually appears in those chunks
  3. Source files of the chunks

This isolates the RAG pipeline (retrieval+rerank) from the LLM's ability
to extract an answer."""

import sys, json, urllib.request
import openpyxl
sys.stdout.reconfigure(encoding="utf-8")

T = "ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI"
KB_SMALL = "055ff3d2478b11f180e77faa71318e24"  # test_five_files (44 docs)

# Load Excel rows that failed
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

print(f"Auditing {len(failing_rows)} failing rows\n")


def post(path, body):
    req = urllib.request.Request(
        f"http://localhost:9380{path}",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {T}",
                 "Content-Type": "application/json; charset=utf-8"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=180).read().decode("utf-8"))


for row_idx, nohel, q, gold in failing_rows:
    print("=" * 80)
    print(f"ROW {row_idx} (נוהל={nohel})")
    print(f"Q: {q[:90]}")
    print(f"GOLD: {gold[:120]}")

    # Run retrieval — what RAGFlow returns BEFORE LLM
    resp = post("/api/v1/retrieval", {
        "dataset_ids": [KB_SMALL],
        "question": q.strip(),
        "top_k": 10,
        "similarity_threshold": 0.0,
    })
    chunks = resp.get("data", {}).get("chunks", [])
    print(f"  retrieved {len(chunks)} chunks")

    # Take 3 distinctive words from the gold answer (length >= 4, not common)
    common = {"של", "על", "את", "אם", "כי", "אינו", "אינה", "המידע", "הוא", "היא"}
    gold_words = [w for w in gold.split() if len(w) >= 4 and w not in common][:5]
    print(f"  searching for any of these gold words in chunks: {gold_words}")

    found_in_top3 = False
    found_anywhere = False
    for i, c in enumerate(chunks):
        if not isinstance(c, dict):
            continue
        content = c.get("content", "")
        sim = c.get("similarity", 0)
        doc = c.get("document_keyword", "?").replace("טסט/", "")
        hits = sum(1 for w in gold_words if w in content)
        marker = ""
        if hits >= 2:
            marker = f"  ★★ has {hits}/{len(gold_words)} gold words"
            found_anywhere = True
            if i < 3:
                found_in_top3 = True
        elif hits == 1:
            marker = f"  ★ has 1 gold word"
        print(f"    [{i+1}] sim={sim:.3f}  doc={doc[:25]:25s}  {marker}")

    print(f"  >>> gold-answer-content in top 3? {'YES' if found_in_top3 else 'NO'}")
    print(f"  >>> gold-answer-content in top 10? {'YES' if found_anywhere else 'NO'}")
    print()

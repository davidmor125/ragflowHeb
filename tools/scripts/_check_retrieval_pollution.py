"""For each failed question, run a /retrieval call directly and see:
  - How many chunks come back from the *expected* נוהל file
  - How many come from other files
  - What's the rank of the first chunk from the right file?

If the right file is dropping out of top-K because of cross-doc noise,
that's the cause."""

import sys, json, urllib.request
sys.stdout.reconfigure(encoding="utf-8")

T = "ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI"
KB_ID = "dc0091ca46e211f196f633ac796a3d7a"

# The 4 questions where the model said "no info" but info exists
CASES = [
    ("20071", "במערכת תמנון+, בעת דיווח על פעולה בלתי רגילה, מתי יש לדווח על ההחלטה \"תקין\""),
    ("20071", "במערכת תמנון+, בעת דיווח על פעולה בלתי רגילה, מתי יש לדווח על ההחלטה \"תקין\""),  # same as above (duplicated row)
    ("20071", "לקוח שלי מבקש להעביר כסף לרוסיה בגין רכישת דירה. האם עלי לדווח על פעולה בלתי רגילה"),
    ("20064", "האם בדוח חריגים מול הצהרות לקוח כלולות הפקדות מזומן מעל 5,000 ₪"),
]


def post(path, body):
    req = urllib.request.Request(
        f"http://localhost:9380{path}",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {T}",
                 "Content-Type": "application/json; charset=utf-8"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=120).read().decode("utf-8"))


for expected_nohel, q in CASES:
    print(f"\n{'=' * 70}")
    print(f"Q: {q[:90]}")
    print(f"  expected נוהל: {expected_nohel}")

    resp = post("/api/v1/retrieval", {
        "dataset_ids": [KB_ID],
        "question": q,
        "top_k": 30,             # request many to see distribution
        "similarity_threshold": 0.0,
        "highlight": False,
    })

    chunks = resp.get("data", {})
    if isinstance(chunks, dict):
        chunks = chunks.get("chunks", [])
    if not isinstance(chunks, list):
        print(f"  unexpected response: {str(resp)[:200]}")
        continue

    # Group by source filename
    by_doc = {}
    for c in chunks:
        if not isinstance(c, dict):
            continue
        name = c.get("docnm_kwd") or c.get("document_name") or c.get("doc_name", "?")
        sim = c.get("similarity", 0)
        by_doc.setdefault(name, []).append(sim)

    print(f"  retrieved {len(chunks)} chunks from {len(by_doc)} different files")

    expected_marker = f"{expected_nohel}.html"
    found_in_expected = False
    rank_of_first_correct = None
    for i, c in enumerate(chunks):
        if not isinstance(c, dict):
            continue
        name = c.get("docnm_kwd") or c.get("document_name") or c.get("doc_name", "?")
        if expected_marker in name:
            if rank_of_first_correct is None:
                rank_of_first_correct = i + 1
            found_in_expected = True

    print(f"  expected file ({expected_marker}) appears: {'YES' if found_in_expected else 'NO!'}")
    if rank_of_first_correct:
        print(f"  rank of first chunk from expected file: #{rank_of_first_correct}")
    print(f"  top 5 docs by chunk count:")
    sorted_docs = sorted(by_doc.items(), key=lambda x: -len(x[1]))[:5]
    for name, sims in sorted_docs:
        marker = " <-- EXPECTED" if expected_marker in name else ""
        print(f"    {len(sims)}x  {name[:60]}  best_sim={max(sims):.3f}{marker}")

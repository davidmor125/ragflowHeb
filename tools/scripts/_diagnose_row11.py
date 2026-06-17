"""Deep dive on Row 11: 'רוסיה'.
Question: 'לקוח שלי מבקש להעביר כסף לרוסיה בגין רכישת דירה. האם עלי לדווח על פעולה בלתי רגילה'
Gold: 'בשל השחיתות השלטונית הנרחבת בכל דרגי הממשל הרוסי, רוסיה מהווה מקור לחשש להלבנת הון...'

Hypothesis to test:
  A. Chunk doesn't exist (chunking destroyed it)
  B. Chunk exists but embeddings score it badly (semantic gap)
  C. Chunk exists but reranker pushed it down
  D. Word 'רוסיה' isn't in any chunk at all (file misclassified)
"""

import sys, json, urllib.request, re
sys.stdout.reconfigure(encoding="utf-8")

T = "ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI"
KB = "055ff3d2478b11f180e77faa71318e24"

def post(path, body):
    req = urllib.request.Request(
        f"http://localhost:9380{path}",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {T}",
                 "Content-Type": "application/json; charset=utf-8"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=180).read().decode("utf-8"))


# ============================================================
# Test A: Does any chunk in the KB contain the word "רוסיה"?
# ============================================================
print("=" * 70)
print("TEST A: Direct retrieval with the gold-answer phrase itself")
print("=" * 70)
r = post("/api/v1/retrieval", {
    "dataset_ids": [KB],
    "question": "רוסיה השחיתות השלטונית הלבנת הון",
    "top_k": 10,
    "similarity_threshold": 0.0,
})
chunks = r["data"]["chunks"]
for i, c in enumerate(chunks[:5]):
    sim = c.get("similarity", 0)
    doc = c.get("document_keyword", "?")
    contains_russia = "רוסיה" in c.get("content", "") or "רוסי" in c.get("content", "")
    snippet = re.sub(r"\s+", " ", c.get("content", ""))[:120]
    print(f"  [{i+1}] sim={sim:.3f}  has_russia={contains_russia}  {doc[:30]}")
    print(f"      {snippet}")


# ============================================================
# Test B: Search with just "רוסיה"
# ============================================================
print("\n" + "=" * 70)
print("TEST B: Direct retrieval with just 'רוסיה'")
print("=" * 70)
r = post("/api/v1/retrieval", {
    "dataset_ids": [KB],
    "question": "רוסיה",
    "top_k": 10,
    "similarity_threshold": 0.0,
})
chunks = r["data"]["chunks"]
russia_chunks = []
for i, c in enumerate(chunks[:10]):
    sim = c.get("similarity", 0)
    doc = c.get("document_keyword", "?")
    content = c.get("content", "")
    has = "רוסיה" in content
    if has:
        russia_chunks.append((i+1, sim, doc, content))
        idx = content.find("רוסיה")
        snippet = content[max(0, idx-60):idx+120]
    else:
        snippet = re.sub(r"\s+", " ", content)[:120]
    print(f"  [{i+1}] sim={sim:.3f}  has_russia={has}  {doc[:30]}")
    print(f"      ...{snippet}...")

print(f"\nFound {len(russia_chunks)} chunks containing 'רוסיה' in top-10")


# ============================================================
# Test C: Run the actual user question with high top_k
# ============================================================
print("\n" + "=" * 70)
print("TEST C: User's actual verbose question with top_k=30")
print("=" * 70)
user_q = "לקוח שלי מבקש להעביר כסף לרוסיה בגין רכישת דירה. האם עלי לדווח על פעולה בלתי רגילה"
r = post("/api/v1/retrieval", {
    "dataset_ids": [KB],
    "question": user_q,
    "top_k": 30,
    "similarity_threshold": 0.0,
})
chunks = r["data"]["chunks"]
print(f"\nLooking for 'רוסיה' in top-30 results of user's question:")
russia_rank = None
for i, c in enumerate(chunks):
    if "רוסיה" in c.get("content", ""):
        russia_rank = i + 1
        sim = c.get("similarity", 0)
        doc = c.get("document_keyword", "?")
        content = c.get("content", "")
        idx = content.find("רוסיה")
        print(f"  ✓ FOUND at rank #{russia_rank}, sim={sim:.3f}, doc={doc}")
        print(f"      ...{content[max(0,idx-60):idx+180]}...")
        break
if russia_rank is None:
    print(f"  ✗ NOT FOUND in top-30 of the user's verbose question")
    # Show top 5 of what RAGFlow does return
    print("\n  What RAGFlow returns instead:")
    for i, c in enumerate(chunks[:5]):
        snip = re.sub(r"\s+", " ", c.get("content", ""))[:100]
        print(f"    [{i+1}] sim={c.get('similarity',0):.3f}  {c.get('document_keyword','?')[:30]}  {snip}")


# ============================================================
# Test D: Check which file actually contains the Russia text
# ============================================================
print("\n" + "=" * 70)
print("TEST D: Source file of the Russia chunk")
print("=" * 70)
if russia_chunks:
    print(f"  Russia chunks come from: {set(c[2] for c in russia_chunks)}")
    print(f"  Excel said expected file: 20071.html")

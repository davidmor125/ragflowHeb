"""For Row 12 specifically — check if the chunk with the answer
(in 20064.html with the threshold 10K/25K) actually reaches the top_n=20
that the LLM sees."""
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
    return json.loads(urllib.request.urlopen(req, timeout=300).read().decode("utf-8"))


# The question RAGFlow gets
user_q = "האם בדוח חריגים מול הצהרות לקוח כלולות הפקדות מזומן מעל 5,000 ₪"

# What's in chunks for top_n=20 of this question?
print(f"USER QUESTION: {user_q}\n")
r = post("/api/v1/retrieval", {
    "dataset_ids": [KB],
    "question": user_q,
    "top_k": 20,
    "similarity_threshold": 0.1,
})
chunks = r["data"]["chunks"]
print(f"Top {len(chunks)} chunks delivered:")
for i, c in enumerate(chunks):
    sim = c.get("similarity", 0)
    doc = c.get("document_keyword", "?")
    content = c.get("content", "")
    has_10k = "10,000" in content or "10000" in content
    has_25k = "25,000" in content or "25000" in content
    has_doch = "דוח" in content and "חריגים" in content and "הצהר" in content
    has_hapk = "הפקד" in content and "מזומן" in content
    flags = []
    if has_10k: flags.append("10K")
    if has_25k: flags.append("25K")
    if has_doch: flags.append("DOCH")
    if has_hapk: flags.append("$$$")
    snippet = re.sub(r"\s+", " ", content)[:150]
    marker = "  ★★★" if (has_10k and has_doch) else ("  ★" if has_doch else "")
    print(f"  [{i+1:2d}] sim={sim:.3f} {' '.join(flags):15s} {doc[:25]:25s}{marker}")
    if has_10k or has_doch:
        print(f"        content: {snippet}")

# Did the gold-answer chunk reach top-20?
print("\n=== ANSWER ===")
gold_in_top = False
for i, c in enumerate(chunks):
    content = c.get("content", "")
    if "10,000" in content and "דוח" in content and "חריגים" in content:
        print(f"  ✓ GOLD ANSWER CHUNK reached top {i+1}!")
        gold_in_top = True
        break
if not gold_in_top:
    print(f"  ✗ GOLD ANSWER CHUNK (with '10,000' + 'דוח חריגים') NOT in top {len(chunks)}")

# Now check: where IS this chunk if we search for it directly?
print("\n=== Where does the gold chunk rank when searched directly? ===")
r2 = post("/api/v1/retrieval", {
    "dataset_ids": [KB],
    "question": "סכום מינימום הפקדות מזומן 10,000 ₪ דוח חריגים",
    "top_k": 30,
    "similarity_threshold": 0.0,
})
for i, c in enumerate(r2["data"]["chunks"]):
    content = c.get("content", "")
    if "10,000" in content and "דוח" in content and "חריגים" in content:
        sim = c.get("similarity", 0)
        doc = c.get("document_keyword", "?")
        print(f"  Found at rank #{i+1}, sim={sim:.3f}, doc={doc}")
        snippet = re.sub(r"\s+", " ", content)[:300]
        print(f"  content: {snippet}")
        break

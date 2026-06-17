"""Compare what RAGFlow returns for the user's actual question vs the gold-answer phrasing."""
import sys, json, urllib.request
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

# Find which chunk has the gold answer
gold_phrase = "לאחר בדיקת הסניף, נמצא כי הפעולה אינה חייבת בדיווח"
print(f"GOLD chunk look-up by exact phrase '{gold_phrase[:50]}...':")
r = post("/api/v1/retrieval", {"dataset_ids":[KB], "question":gold_phrase, "top_k":3})
for c in r["data"]["chunks"][:3]:
    print(f"  sim={c['similarity']:.3f} doc={c['document_keyword']} content_starts={c['content'][:80]!r}")
gold_chunk_id = r["data"]["chunks"][0]["id"]
print(f"\nGOLD chunk ID: {gold_chunk_id}\n")

# Now search with the actual user question
queries = [
    "במערכת תמנון+, בעת דיווח על פעולה בלתי רגילה, מתי יש לדווח על ההחלטה תקין",
    "מתי לדווח על החלטה תקין",
    "החלטה תקין דיווח",
    "פעולה לא חייבת בדיווח",
    'מתי יש לסמן "תקין" בדיווח',
]
for q in queries:
    print("=" * 60)
    print(f"Query: {q}")
    r = post("/api/v1/retrieval", {"dataset_ids":[KB], "question":q, "top_k":15, "similarity_threshold":0.0})
    chunks = r["data"]["chunks"]
    rank = None
    for i, c in enumerate(chunks):
        if c.get("id") == gold_chunk_id:
            rank = i + 1
            print(f"  ✓ GOLD chunk found at rank #{rank}, sim={c['similarity']:.3f}")
            break
    if rank is None:
        print(f"  ✗ GOLD chunk NOT in top-15. Top results:")
        for i, c in enumerate(chunks[:5]):
            print(f"    [{i+1}] sim={c['similarity']:.3f} doc={c['document_keyword'][:30]} content={c['content'][:60]!r}")
    print()

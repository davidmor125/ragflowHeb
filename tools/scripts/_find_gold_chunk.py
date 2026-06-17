"""Find which chunks in the KB actually contain the gold-answer phrase
(verbatim or close to it). If they exist but RAGFlow doesn't surface them,
the issue is retrieval ranking. If they don't exist, the issue is chunking."""

import sys, json, urllib.request, subprocess
sys.stdout.reconfigure(encoding="utf-8")

T = "ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI"
KB_SMALL = "055ff3d2478b11f180e77faa71318e24"

# Phrases that should appear if the gold answer is in any chunk
gold_phrases = [
    "לאחר בדיקת הסניף",
    "אינה חייבת בדיווח",
    "יש לפרט את תיאור המקרה",
    "החלטה כי הפעולה אינה",
]

# Get every chunk in the 20071.html document and search for the gold phrases
def post(path, body):
    req = urllib.request.Request(
        f"http://localhost:9380{path}",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {T}",
                 "Content-Type": "application/json; charset=utf-8"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=180).read().decode("utf-8"))

# Get all chunks in the small KB - using a broad retrieval call
# We query with each gold phrase as the question to find which chunk has it
print(f"Searching {KB_SMALL} for chunks containing gold-answer phrases\n")

for phrase in gold_phrases:
    print(f"Searching for: {phrase!r}")
    resp = post("/api/v1/retrieval", {
        "dataset_ids": [KB_SMALL],
        "question": phrase,
        "top_k": 5,
        "similarity_threshold": 0.0,
    })
    chunks = resp.get("data", {}).get("chunks", [])
    found = False
    for i, c in enumerate(chunks):
        if not isinstance(c, dict):
            continue
        content = c.get("content", "")
        sim = c.get("similarity", 0)
        doc = c.get("document_keyword", "?")
        if phrase in content:
            found = True
            idx = content.find(phrase)
            print(f"  ✓ FOUND in chunk #{i+1} sim={sim:.3f} doc={doc}")
            print(f"    context: ...{content[max(0,idx-60):idx+120]}...")
            break
    if not found:
        print(f"  ✗ phrase NOT found verbatim in top-5 chunks")
        # Try fuzzy: any chunk with at least 2 of these words
        words = phrase.split()
        for i, c in enumerate(chunks[:3]):
            if not isinstance(c, dict):
                continue
            hits = sum(1 for w in words if w in c.get("content", ""))
            print(f"    [{i+1}] sim={c.get('similarity',0):.3f} {c.get('document_keyword','?')}: has {hits}/{len(words)} words")
    print()

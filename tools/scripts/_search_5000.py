"""Search the raw file 20064.html for any mention of 5,000 ₪ or 5000.
Also search all chunks of that document in the KB."""
import sys, json, urllib.request, re
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

T = "ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI"
KB = "055ff3d2478b11f180e77faa71318e24"

# 1. Search the raw HTML
print("=" * 70)
print("TEST 1: Search the RAW 20064.html file for 5,000 / 5000")
print("=" * 70)
raw_paths = [
    Path(r"C:/develop/html_output/_eval_report/newtest/טסט/20064.html"),
]
for p in raw_paths:
    if not p.exists():
        print(f"  not found: {p}")
        continue
    text = p.read_text(encoding="utf-8", errors="ignore")
    print(f"  file: {p.name}, size: {len(text)} chars")
    # Look for 5,000 / 5000 / 5,000 ש"ח / 5,000 ₪
    patterns = [r"5,000", r"5000\s*₪", r"5000\s*ש\"ח", r"5,000\s*₪", r"5,000\s*ש\"ח", r'5,000\s*ש"ח']
    for pat in patterns:
        matches = list(re.finditer(pat, text))
        print(f"  pattern {pat!r}: {len(matches)} matches")
        for m in matches[:3]:
            start = max(0, m.start() - 100)
            end = min(len(text), m.end() + 200)
            ctx = re.sub(r"<[^>]+>", "", text[start:end])
            ctx = re.sub(r"\s+", " ", ctx)
            print(f"    context: ...{ctx}...")

# 2. Search all chunks of 20064.html in the KB by document_keyword
print("\n" + "=" * 70)
print("TEST 2: Find chunks of 20064.html that contain 5,000")
print("=" * 70)

def post(path, body):
    req = urllib.request.Request(
        f"http://localhost:9380{path}",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {T}",
                 "Content-Type": "application/json; charset=utf-8"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=180).read().decode("utf-8"))

# Search with 5000 as keyword
r = post("/api/v1/retrieval", {
    "dataset_ids": [KB],
    "question": "5,000 הפקדות מזומן דוח חריגים",
    "top_k": 30,
    "similarity_threshold": 0.0,
})
chunks = r["data"]["chunks"]
matches_in_20064 = []
for i, c in enumerate(chunks):
    doc = c.get("document_keyword", "?")
    content = c.get("content", "")
    if "20064" not in doc:
        continue
    has_5k = "5,000" in content or "5000" in content
    if has_5k:
        matches_in_20064.append((i+1, c.get("similarity", 0), content))
        idx = max(content.find("5,000"), content.find("5000"))
        snippet = content[max(0,idx-150):idx+300]
        snippet = re.sub(r"<[^>]+>", "", snippet)
        snippet = re.sub(r"\s+", " ", snippet)
        print(f"  rank #{i+1} sim={c.get('similarity',0):.3f} doc=20064.html")
        print(f"    snippet: ...{snippet}...")
        print()

print(f"\nTotal 20064.html chunks containing 5,000: {len(matches_in_20064)}")

"""Inspect actual chunks for a specific document via RAGFlow API,
to see if Hebrew chunking is sane (sentences not torn, RTL preserved,
chunks coherent)."""

import sys
import json
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

T = "ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI"
KB_ID = "dc0091ca46e211f196f633ac796a3d7a"
TARGET_FILE = "20071.html"  # the one row 9-10 questions hit


def get(path):
    req = urllib.request.Request(
        f"http://localhost:9380{path}",
        headers={"Authorization": f"Bearer {T}"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))


# 1. Find the document id by name. List docs in KB.
docs_resp = get(f"/api/v1/datasets/{KB_ID}/documents?page=1&page_size=1000")
docs = docs_resp.get("data", {}).get("docs") or docs_resp.get("data") or []
if isinstance(docs, dict):
    docs = docs.get("docs") or docs.get("items") or []

doc_id = None
for d in docs:
    if isinstance(d, dict):
        name = d.get("name") or d.get("filename", "")
        if name.endswith(TARGET_FILE) or name == TARGET_FILE:
            doc_id = d.get("id")
            print(f"found doc: name={name!r} id={doc_id} chunk_count={d.get('chunk_count')}")
            break

if not doc_id:
    print(f"docs sample: {[d.get('name') if isinstance(d, dict) else d for d in docs[:5]]}")
    print(f"could not find {TARGET_FILE}")
    raise SystemExit(1)

# 2. Get its chunks
chunks_resp = get(f"/api/v1/datasets/{KB_ID}/documents/{doc_id}/chunks?page=1&page_size=20")
chunks = chunks_resp.get("data", {})
if isinstance(chunks, dict):
    chunk_list = chunks.get("chunks") or chunks.get("items") or []
    total = chunks.get("total", len(chunk_list))
else:
    chunk_list = chunks if isinstance(chunks, list) else []
    total = len(chunk_list)

print(f"\n=== CHUNKS (showing first 8 of {total}) ===\n")
for i, c in enumerate(chunk_list[:8]):
    if not isinstance(c, dict):
        print(f"chunk {i}: {str(c)[:200]}")
        continue
    content = c.get("content") or c.get("content_with_weight") or c.get("text", "")
    print(f"--- CHUNK {i} (id={c.get('id', '?')[:12]}, len={len(content)}) ---")
    print(content[:600])
    print()

"""Debug failed questions: see what chunks were retrieved and check if the gold-answer phrases are actually in the parsed document."""
import sys, os, json, re
sys.stdout.reconfigure(encoding='utf-8')
import requests, pymysql

BASE_URL = 'http://localhost:9380'
API_KEY  = 'ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
KB_ID    = 'dc0091ca46e211f196f633ac796a3d7a'
DOC_ID   = 'f84ca83246e211f196f633ac796a3d7a'
TENANT   = '2507563a42bd11f1a6bba9e87ac7a32c'
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# === 1. Pull all chunks of the doc directly from Elasticsearch ===
print("=" * 75, flush=True)
print("STEP 1: Pull all chunks of doc 32904 from Elasticsearch", flush=True)
print("=" * 75, flush=True)

from elasticsearch import Elasticsearch
es = Elasticsearch("http://localhost:1200", basic_auth=("elastic", "infini_rag_flow"))
INDEX = f"ragflow_{TENANT}"

resp = es.search(
    index=INDEX,
    body={
        "size": 200,
        "query": {"bool": {"must": [
            {"term": {"kb_id": KB_ID}},
            {"term": {"doc_id": DOC_ID}}
        ]}},
        "_source": ["content_with_weight", "important_kwd", "question_kwd", "title_tks"],
    }
)
hits = resp['hits']['hits']
print(f"Total chunks in doc 32904: {len(hits)}\n", flush=True)

# === 2. Search the chunks for golden-answer key phrases ===
KEY_PHRASES = {
    "Q69-71 (גנרי)": [
        "חוק שירותי תשלום",
        "ביטול כרטיס בהודעה",
        "אין להתנות את הביטול בהחזרת הכרטיס",
        "פרונטלית",
        "טלפונית",
        "התכתבות",
    ],
    "Q72 (עמלות)": [
        "ריכוז תעריפוני",
        "תעריפון",
        "עמלות",
    ],
    "Q68 (שימור)": [
        "שימור",
        "מועדונים",
        "32919",
        "כרטיס חליפי",
        "אובדן",
    ],
}

print("=" * 75, flush=True)
print("STEP 2: Search chunks for golden-answer key phrases", flush=True)
print("=" * 75, flush=True)

found_chunks = {}
for label, phrases in KEY_PHRASES.items():
    print(f"\n--- {label} ---", flush=True)
    for phrase in phrases:
        matches = []
        for h in hits:
            content = (h['_source'].get('content_with_weight') or '')
            if phrase in content:
                matches.append((h['_id'], content))
        marker = "✓" if matches else "✗"
        print(f"  {marker} '{phrase}'  found in {len(matches)} chunks", flush=True)
        if matches:
            found_chunks.setdefault(label, []).append((phrase, matches[0]))

# === 3. Show snippets that contain the key phrases ===
print("\n" + "=" * 75, flush=True)
print("STEP 3: Snippets with key phrases (first match per phrase)", flush=True)
print("=" * 75, flush=True)

for label, items in found_chunks.items():
    print(f"\n=== {label} ===", flush=True)
    for phrase, (chunk_id, content) in items:
        idx = content.find(phrase)
        snip_start = max(0, idx - 100)
        snip_end = min(len(content), idx + len(phrase) + 200)
        snip = content[snip_start:snip_end].replace("\n", " ")
        print(f"\n  [{phrase}] in chunk {chunk_id[:16]}...:", flush=True)
        print(f"  ...{snip}...", flush=True)

# === 4. Check what chunks were retrieved for failed questions via /retrieval API ===
print("\n" + "=" * 75, flush=True)
print("STEP 4: Test retrieval directly for the failed questions", flush=True)
print("=" * 75, flush=True)

FAILED_QS = [
    ("Q69 ויזה כאל", "איך ניתן לבטל כרטיס מסוג ויזה כאל?"),
    ("Q71 מקס",     "איך מבטלים כרטיס אשראי מסוג מקס?"),
    ("Q72 עלות",    "כמה עולה לבטל כרטיס אשראי?"),
]

for label, q in FAILED_QS:
    print(f"\n--- {label} ---", flush=True)
    print(f"  Q: {q}", flush=True)
    body = {
        "question": q,
        "dataset_ids": [KB_ID],
        "document_ids": [DOC_ID],
        "similarity_threshold": 0.1,
        "vector_similarity_weight": 0.3,
        "top_k": 1024,
        "page_size": 10,
    }
    r = requests.post(f"{BASE_URL}/api/v1/retrieval", json=body, headers=HEADERS, timeout=60)
    if r.status_code != 200:
        print(f"  HTTP {r.status_code}: {r.text[:300]}", flush=True)
        continue
    j = r.json()
    if j.get('code') != 0:
        print(f"  ERROR: {j.get('message')}", flush=True)
        continue
    data = j.get('data', {})
    chunks = data.get('chunks', [])
    print(f"  retrieved {len(chunks)} chunks", flush=True)
    for i, c in enumerate(chunks[:5]):
        content = (c.get('content') or '')[:300].replace("\n", " ")
        sim = c.get('similarity') or c.get('vector_similarity') or 0
        print(f"  [{i+1}] sim={sim:.3f}  doc_id={(c.get('document_id') or '')[:8]}", flush=True)
        print(f"      {content}...", flush=True)

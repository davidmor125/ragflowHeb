"""For each failed question, ask the RAGFlow retrieval API which chunks of doc 32904
were returned and at what similarity score. Then check whether the gold-answer phrases
appear inside those chunks.
"""
import sys, json, re
sys.stdout.reconfigure(encoding='utf-8')
import requests

BASE_URL = 'http://localhost:9380'
API_KEY  = 'ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
KB_ID    = 'dc0091ca46e211f196f633ac796a3d7a'
DOC_ID   = 'f84ca83246e211f196f633ac796a3d7a'
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

QUESTIONS = [
    {
        "n": 68, "q": "איך ניתן לבטל כרטיס אשראי בהתכתבות עם בנקאי?",
        "gold_phrases": ["שימור", "מועדונים", "32919", "כרטיס חליפי", "טלפונית"],
        "passed": True,
    },
    {
        "n": 69, "q": "איך ניתן לבטל כרטיס מסוג ויזה כאל?",
        "gold_phrases": ["חוק שירותי תשלום", "ביטול כרטיס בהודעה", "פרונטלית", "טלפונית", "התכתבות"],
        "passed": False,
    },
    {
        "n": 70, "q": "איך ניתן לבטל כרטיס של ישראכרט?",
        "gold_phrases": ["חוק שירותי תשלום", "ביטול כרטיס בהודעה", "פרונטלית", "טלפונית", "התכתבות"],
        "passed": True,
    },
    {
        "n": 71, "q": "איך מבטלים כרטיס אשראי מסוג מקס?",
        "gold_phrases": ["חוק שירותי תשלום", "ביטול כרטיס בהודעה", "פרונטלית", "טלפונית", "התכתבות"],
        "passed": False,
    },
    {
        "n": 72, "q": "כמה עולה לבטל כרטיס אשראי?",
        "gold_phrases": ["ריכוז תעריפוני", "תעריפון", "עמלות"],
        "passed": False,
    },
]

# Try multiple retrieval endpoint variants — different versions name it differently
def call_retrieval(question, k=25):
    body = {
        "question": question,
        "dataset_ids": [KB_ID],
        "document_ids": [DOC_ID],
        "similarity_threshold": 0.1,
        "vector_similarity_weight": 0.3,
        "top_k": 1024,
        "page_size": k,
    }
    for path in ["/api/v1/retrieval", "/v1/chunk/retrieval_test"]:
        r = requests.post(f"{BASE_URL}{path}", json=body, headers=HEADERS, timeout=60)
        if r.status_code == 200:
            try:
                j = r.json()
                if j.get('code') == 0:
                    return path, j['data']
            except Exception:
                pass
    # legacy form
    legacy_body = {
        "kb_id": [KB_ID],
        "doc_ids": [DOC_ID],
        "question": question,
        "similarity_threshold": 0.1,
        "vector_similarity_weight": 0.3,
        "top_k": 1024,
        "size": k,
    }
    r = requests.post(f"{BASE_URL}/v1/chunk/retrieval_test", json=legacy_body, headers=HEADERS, timeout=60)
    if r.status_code == 200:
        try:
            j = r.json()
            if j.get('code') == 0:
                return "/v1/chunk/retrieval_test (legacy body)", j['data']
        except Exception:
            pass
    return None, {"error": r.text[:300], "status": r.status_code}


print("=" * 90, flush=True)
print("Retrieval debug: for each question, show top chunks + check for gold phrases", flush=True)
print("=" * 90, flush=True)

for q in QUESTIONS:
    status = "✅ PASS" if q['passed'] else "❌ FAIL"
    print(f"\n\n############## Q{q['n']}  {status}: {q['q']} ##############", flush=True)
    print(f"  Gold-answer phrases: {q['gold_phrases']}", flush=True)
    path, data = call_retrieval(q['q'], k=25)
    if path is None:
        print(f"  Retrieval failed: {data}", flush=True)
        continue
    chunks = data.get('chunks', []) or data.get('items', []) or []
    print(f"  Endpoint: {path}", flush=True)
    print(f"  Got {len(chunks)} chunks", flush=True)

    # Check phrase presence per chunk
    print(f"\n  RANK | sim   |vsim   |term   | gold-phrases hit | preview", flush=True)
    print(f"  -----+-------+-------+-------+------------------+--------", flush=True)
    for i, c in enumerate(chunks[:25]):
        content = c.get('content_with_weight') or c.get('content') or ''
        sim = c.get('similarity', 0) or 0
        vsim = c.get('vector_similarity', 0) or 0
        tsim = c.get('term_similarity', 0) or 0
        hits = [p for p in q['gold_phrases'] if p in content]
        prev = re.sub(r'\s+', ' ', content)[:120]
        marker = "★" if hits else " "
        print(f"  {marker} {i+1:2d} | {sim:.3f} | {vsim:.3f} | {tsim:.3f} | {hits or '—'}", flush=True)
        if hits:
            # show the snippet around the first hit
            for ph in hits:
                idx = content.find(ph)
                start = max(0, idx-60); end = min(len(content), idx+len(ph)+200)
                snip = re.sub(r'\s+', ' ', content[start:end])
                print(f"        >> [{ph}]  ...{snip}...", flush=True)

    # Aggregate: did ANY chunk in the top-25 contain ANY gold phrase?
    any_hit = False
    for c in chunks[:25]:
        content = c.get('content_with_weight') or c.get('content') or ''
        if any(p in content for p in q['gold_phrases']):
            any_hit = True; break
    summary = "✅ retrieval OK (gold phrase IS in returned chunks)" if any_hit else "❌ retrieval MISSED (no chunk has gold phrase)"
    print(f"\n  SUMMARY: {summary}", flush=True)

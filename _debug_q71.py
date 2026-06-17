"""Q71 returned 0 chunks. Run retrieval directly and compare to other questions."""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import requests

BASE_URL = 'http://localhost:9380'
API_KEY = 'ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
KB_ID = 'dc0091ca46e211f196f633ac796a3d7a'
DOC_ID = 'f84ca83246e211f196f633ac796a3d7a'
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

QUESTIONS = [
    ("Q68", "איך ניתן לבטל כרטיס אשראי בהתכתבות עם בנקאי?"),
    ("Q69", "איך ניתן לבטל כרטיס מסוג ויזה כאל?"),
    ("Q70", "איך ניתן לבטל כרטיס של ישראכרט?"),
    ("Q71", "איך מבטלים כרטיס אשראי מסוג מקס?"),
    ("Q72", "כמה עולה לבטל כרטיס אשראי?"),
]

for label, q in QUESTIONS:
    body = {
        "question": q,
        "dataset_ids": [KB_ID],
        # NOTE: NOT restricted to doc 32904 - let it pull from whole KB
        "similarity_threshold": 0.1,
        "vector_similarity_weight": 0.3,
        "top_k": 1024,
        "page_size": 10,
    }
    r = requests.post(f"{BASE_URL}/api/v1/retrieval", json=body, headers=HEADERS, timeout=60)
    j = r.json()
    chunks = (j.get('data') or {}).get('chunks', [])
    print(f"\n=== {label}: {q} ===")
    print(f"  total retrieved: {len(chunks)}")
    for i, c in enumerate(chunks[:6]):
        content = (c.get('content_with_weight') or c.get('content') or '')[:180].replace("\n", " ")
        sim = c.get('similarity', 0)
        vsim = c.get('vector_similarity', 0)
        tsim = c.get('term_similarity', 0)
        doc_id = c.get('document_id', '')[:8]
        doc_name = c.get('document_keyword', '')
        kwd = c.get('important_kwd', [])
        print(f"  [{i+1}] sim={sim:.3f} vsim={vsim:.3f} tsim={tsim:.3f}  doc={doc_id}({doc_name})")
        print(f"      kwd={kwd}")
        print(f"      {content}")

# Also try Q71 with rephrasing
print("\n\n=== Q71 variants ===")
for variant in [
    "איך מבטלים כרטיס אשראי מסוג מקס?",
    "כיצד מבטלים כרטיס מקס?",
    "ביטול כרטיס מקס",
    "ביטול כרטיס MAX",
    "max ביטול",
    "איך מבטלים כרטיס?",
]:
    body = {
        "question": variant,
        "dataset_ids": [KB_ID],
        "similarity_threshold": 0.1,
        "vector_similarity_weight": 0.3,
        "top_k": 1024,
        "page_size": 5,
    }
    r = requests.post(f"{BASE_URL}/api/v1/retrieval", json=body, headers=HEADERS, timeout=60)
    j = r.json()
    chunks = (j.get('data') or {}).get('chunks', [])
    print(f"  variant={variant!r}: {len(chunks)} chunks")
    for c in chunks[:2]:
        content = (c.get('content_with_weight') or '')[:140].replace("\n"," ")
        sim = c.get('similarity', 0)
        print(f"    sim={sim:.3f} {content}")

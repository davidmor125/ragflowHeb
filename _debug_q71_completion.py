"""Run Q71 specifically through completion and inspect what comes back."""
import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests

BASE = 'http://localhost:9380'
API_KEY = 'ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
CHAT_ID = 'cf68bf1a46f011f196f633ac796a3d7a'
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# Create fresh session
r = requests.post(f"{BASE}/api/v1/chats/{CHAT_ID}/sessions",
                  json={"name":f"q71-debug-{int(time.time())}"}, headers=HEADERS, timeout=30)
sid = r.json()['data']['id']
print(f"session={sid}")

# Run Q71 with streaming so we can see ALL events
body = {"question": "איך מבטלים כרטיס אשראי מסוג מקס?", "stream": True, "session_id": sid}
r = requests.post(f"{BASE}/api/v1/chats/{CHAT_ID}/completions", json=body, headers=HEADERS, timeout=300, stream=True)

print(f"HTTP {r.status_code}")
final_answer = ""
final_reference = None
for line in r.iter_lines(decode_unicode=True):
    line = (line or '').strip()
    if not line.startswith('data:'):
        continue
    payload = line[5:].strip()
    if payload in ('', '[DONE]'):
        continue
    try:
        obj = json.loads(payload)
    except Exception:
        continue
    data = obj.get('data')
    if isinstance(data, dict):
        ans = data.get('answer', '')
        if isinstance(ans, str) and ans and ans != final_answer:
            final_answer = ans
        ref = data.get('reference')
        if isinstance(ref, dict) and ref:
            final_reference = ref

print("\n=== FINAL ANSWER ===")
print(final_answer[:800])
print("\n=== REFERENCE ===")
if final_reference:
    chunks = final_reference.get('chunks', [])
    print(f"chunks: {len(chunks)}")
    for i, c in enumerate(chunks[:5]):
        content = (c.get('content_with_weight') or c.get('content') or '')[:200].replace("\n", " ")
        print(f"  [{i+1}] sim={c.get('similarity',0):.3f}  doc={(c.get('document_id') or '')[:8]}  {content}")
else:
    print("(no reference)")

# Also try without "keyword" expansion - it's a Dialog flag
# Note: can't disable that per-request, but can try with same query directly through retrieval
print("\n=== Retrieval direct (no Dialog) ===")
body2 = {
    "question": "איך מבטלים כרטיס אשראי מסוג מקס?",
    "dataset_ids": ["dc0091ca46e211f196f633ac796a3d7a"],
    "similarity_threshold": 0.1,
    "vector_similarity_weight": 0.3,
    "top_k": 1024,
    "page_size": 25,
}
r2 = requests.post(f"{BASE}/api/v1/retrieval", json=body2, headers=HEADERS, timeout=60)
chunks2 = (r2.json().get('data') or {}).get('chunks', [])
print(f"chunks: {len(chunks2)}")
for i, c in enumerate(chunks2[:5]):
    content = (c.get('content_with_weight') or '')[:180].replace("\n", " ")
    print(f"  [{i+1}] sim={c.get('similarity',0):.3f}  doc={(c.get('document_id') or '')[:8]}  {content}")

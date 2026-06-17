"""Probe RAGFlow chat endpoint to see actual response shape."""
import sys
import json
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

TOKEN = "ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI"
BASE = "http://localhost:9380"

def get(path):
    req = urllib.request.Request(
        BASE + path,
        headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))

def post(path, body):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
        },
        method="POST",
    )
    return json.loads(urllib.request.urlopen(req, timeout=120).read().decode("utf-8"))

# 1. List chats
chats_resp = get("/api/v1/chats?page=1&page_size=20")
print("=== CHATS ===")
print(f"keys: {list(chats_resp.keys())}")
data = chats_resp.get("data", [])
print(f"data type: {type(data).__name__}, count: {len(data) if isinstance(data, (list, dict)) else 'n/a'}")
if isinstance(data, list):
    for c in data:
        if isinstance(c, dict):
            print(f"  - name={c.get('name')!r} id={c.get('id')} kbs={c.get('dataset_ids') or c.get('kb_ids')}")
        else:
            print(f"  - (str): {c[:100]}")
elif isinstance(data, dict):
    print(f"  data dict keys: {list(data.keys())}")

# 2. Try OpenAI completion with the bank-eval chat
print("\n=== TRYING COMPLETION ===")
bank_chat_id = None
if isinstance(data, list):
    for c in data:
        if isinstance(c, dict) and c.get("name") == "bank-eval":
            bank_chat_id = c["id"]
            break
if not bank_chat_id and isinstance(data, list) and data:
    c = data[0]
    if isinstance(c, dict):
        bank_chat_id = c.get("id")

if bank_chat_id:
    print(f"using chat_id={bank_chat_id}")
    try:
        resp = post(f"/api/v1/openai/{bank_chat_id}/chat/completions", {
            "model": "model",
            "messages": [{"role": "user", "content": "מהי מטרת הנוהל לעיון במידע?"}],
            "stream": False,
            "extra_body": {"reference": True},
        })
        print(f"response keys: {list(resp.keys())}")
        # Pretty-print first 1500 chars of the JSON
        s = json.dumps(resp, ensure_ascii=False, indent=2)
        print(s[:2000])
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"HTTPError {e.code}: {body[:500]}")
else:
    print("no chat_id available")

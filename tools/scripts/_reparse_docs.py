"""Trigger reparse on the 5 docs hit by the first 10 questions.

We must also push the new parser_config down to each document row, since
each doc carries its own parser_config copy from when it was first uploaded.
"""
import sys, json, urllib.request, urllib.error, time, subprocess
sys.stdout.reconfigure(encoding="utf-8")

T = "ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI"
KB_ID = "dc0091ca46e211f196f633ac796a3d7a"
TARGET_FILES = ["32328", "20071", "20064", "12917", "34320"]


def http(method, path, body=None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body else None
    req = urllib.request.Request(
        f"http://localhost:9380{path}",
        data=data, method=method,
        headers={"Authorization": f"Bearer {T}",
                 "Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_body": e.read().decode("utf-8", errors="replace")}


# 1. Find doc ids
docs_resp = http("GET", f"/api/v1/datasets/{KB_ID}/documents?page=1&page_size=1000")
docs = docs_resp.get("data", {})
docs = docs.get("docs") if isinstance(docs, dict) else docs
if not docs and isinstance(docs_resp.get("data"), dict):
    docs = docs_resp["data"].get("items", [])

doc_ids = []
for d in docs:
    if isinstance(d, dict):
        name = d.get("name", "")
        for target in TARGET_FILES:
            if name.endswith(f"{target}.html"):
                doc_ids.append((d.get("id"), name, target))
                break
print(f"matched {len(doc_ids)} docs:")
for did, name, t in doc_ids:
    print(f"  {t} -> id={did[:16]} name={name!r}")

if len(doc_ids) != 5:
    print("WARN: expected 5 docs")

# 2. Push new KB parser_config into each doc.
# Get the new KB parser_config:
out = subprocess.run(
    ["docker", "exec", "-i", "docker-mysql-1",
     "mysql", "-u", "root", "-pinfini_rag_flow",
     "--default-character-set=utf8mb4", "-N", "-D", "rag_flow"],
    input=f"SELECT parser_config FROM knowledgebase WHERE id='{KB_ID}';".encode(),
    capture_output=True,
)
kb_cfg_str = out.stdout.decode("utf-8").strip()
print(f"\nKB parser_config (first 200 chars): {kb_cfg_str[:200]}")

# Update each document row's parser_config to match the KB's.
# Use direct SQL since the SDK API may not honor parent_child on PATCH.
ids_quoted = ",".join(f"'{d[0]}'" for d in doc_ids)
update_sql = (
    f"UPDATE document SET parser_config = '{kb_cfg_str.replace(chr(92), chr(92)+chr(92)).replace(chr(39), chr(92)+chr(39))}' "
    f"WHERE id IN ({ids_quoted});"
)
result = subprocess.run(
    ["docker", "exec", "-i", "docker-mysql-1",
     "mysql", "-u", "root", "-pinfini_rag_flow",
     "--default-character-set=utf8mb4", "-D", "rag_flow"],
    input=update_sql.encode("utf-8"),
    capture_output=True,
)
print(f"\nDoc parser_config update: rc={result.returncode}, stderr={result.stderr.decode()[:200]}")

# 3. Trigger parse via API
parse_body = {"document_ids": [d[0] for d in doc_ids]}
parse_resp = http("POST", f"/api/v1/datasets/{KB_ID}/documents/parse", parse_body)
print(f"\nparse trigger response: {json.dumps(parse_resp, ensure_ascii=False)[:300]}")

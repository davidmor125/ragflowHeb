"""Re-parse all 44 docs in test_five_files KB with the new laws parser."""
import sys, json, urllib.request, subprocess
sys.stdout.reconfigure(encoding="utf-8")

T = "ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI"
KB = "055ff3d2478b11f180e77faa71318e24"

# Get all doc IDs in this KB
result = subprocess.run(
    ["docker", "exec", "-i", "docker-mysql-1",
     "mysql", "-u", "root", "-pinfini_rag_flow",
     "--default-character-set=utf8mb4", "-N", "-D", "rag_flow", "-e",
     f"SELECT id, name FROM document WHERE kb_id='{KB}';"],
    capture_output=True,
)
lines = result.stdout.decode("utf-8").strip().split("\n")
docs = [line.split("\t") for line in lines if line]
print(f"Found {len(docs)} docs to reparse")

# Reset all to "not parsed yet" state and clear their chunk_num
ids = ",".join(f"'{d[0]}'" for d in docs)
reset_sql = f"""
UPDATE document SET run='0', chunk_num=0, progress=0, progress_msg='', status='1'
WHERE id IN ({ids});
"""
subprocess.run(
    ["docker", "exec", "-i", "docker-mysql-1",
     "mysql", "-u", "root", "-pinfini_rag_flow",
     "--default-character-set=utf8mb4", "-D", "rag_flow"],
    input=reset_sql.encode("utf-8"), capture_output=True,
)
print("reset all docs to run=0 (not parsed)")

# Trigger parse via API for each doc
def post(path, body):
    req = urllib.request.Request(
        f"http://localhost:9380{path}",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {T}",
                 "Content-Type": "application/json; charset=utf-8"},
    )
    try:
        return json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"_error": e.read().decode()[:200]}

# Use the documents/parse endpoint with all doc IDs at once
doc_ids = [d[0] for d in docs]
resp = post(f"/api/v1/datasets/{KB}/documents/parse", {"document_ids": doc_ids})
print(f"parse trigger response: {json.dumps(resp, ensure_ascii=False)[:300]}")

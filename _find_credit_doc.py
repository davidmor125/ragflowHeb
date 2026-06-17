"""Find credit-cards doc in hozrim KB and matching Dialog."""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')

import pymysql
cfg = dict(host='localhost', port=3306, user='root', password='infini_rag_flow', database='rag_flow', charset='utf8mb4')
conn = pymysql.connect(**cfg, cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()

KB_ID = 'dc0091ca46e211f196f633ac796a3d7a'   # hozrim (647 docs)
TENANT_ID = '2507563a42bd11f1a6bba9e87ac7a32c'

# 1. find 32904 doc in hozrim
cur.execute("""
    SELECT id, name, run, progress, chunk_num, size, parser_id, parser_config
    FROM document
    WHERE kb_id = %s AND name LIKE %s
""", (KB_ID, '%32904%'))
docs = cur.fetchall()
print(f"=== 32904 docs in hozrim ===")
for d in docs:
    print(f"  id={d['id']}  name={d['name']!r}  run={d['run']}  chunks={d['chunk_num']}  size={d['size']}  parser={d['parser_id']}")
    print(f"     parser_config={d['parser_config']!r}")

# 2. List dialogs that include this KB
cur.execute("SELECT id, name, kb_ids, llm_id, prompt_config, top_n, similarity_threshold, vector_similarity_weight FROM dialog")
dialogs = cur.fetchall()
print(f"\n=== Dialogs ({len(dialogs)} total) — those linked to hozrim KB ===")
for d in dialogs:
    kb_ids_raw = d['kb_ids']
    kb_ids = []
    if kb_ids_raw:
        try:
            kb_ids = json.loads(kb_ids_raw) if isinstance(kb_ids_raw, str) else kb_ids_raw
        except Exception:
            kb_ids = []
    if KB_ID in (kb_ids or []):
        print(f"  *** id={d['id']}  name={d['name']!r}  llm={d['llm_id']!r}  top_n={d['top_n']}  sim_thr={d['similarity_threshold']}")

print(f"\n=== All Dialogs (any KB) ===")
for d in dialogs:
    print(f"  id={d['id']}  name={d['name']!r}  llm={d['llm_id']!r}  kb_ids={d['kb_ids']!r:.150}")

cur.close()
conn.close()

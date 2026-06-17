"""Find available LLMs for the tenant - looking for local 20B model."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import pymysql

cfg = dict(host='localhost', port=3306, user='root', password='infini_rag_flow', database='rag_flow', charset='utf8mb4')
conn = pymysql.connect(**cfg, cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
TENANT = '2507563a42bd11f1a6bba9e87ac7a32c'

# tenant LLMs
cur.execute("SELECT * FROM tenant_llm WHERE tenant_id=%s", (TENANT,))
rows = cur.fetchall()
print(f"Tenant LLMs ({len(rows)}):")
for r in rows:
    print(f"  llm_factory={r.get('llm_factory')!r}  model_type={r.get('model_type')!r}  llm_name={r.get('llm_name')!r}  api_base={r.get('api_base')!r}")

# Also from llm table
cur.execute("SELECT llm_name, fid, model_type FROM llm WHERE llm_name LIKE '%20%' OR llm_name LIKE '%gpt%' OR llm_name LIKE '%oss%' ORDER BY llm_name LIMIT 50")
print(f"\nAll LLMs matching gpt/20/oss:")
for r in cur.fetchall():
    print(f"  {r['llm_name']!r}  factory={r['fid']!r}  type={r['model_type']}")

cur.close()
conn.close()

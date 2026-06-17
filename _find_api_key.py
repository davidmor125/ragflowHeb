"""Locate an API token for the tenant so we can call HTTP API."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import pymysql
cfg = dict(host='localhost', port=3306, user='root', password='infini_rag_flow', database='rag_flow', charset='utf8mb4')
conn = pymysql.connect(**cfg, cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
TENANT = '2507563a42bd11f1a6bba9e87ac7a32c'

# api tokens
cur.execute("SHOW TABLES LIKE '%api%'")
print("API tables:", cur.fetchall())
cur.execute("SELECT * FROM api_token WHERE tenant_id=%s", (TENANT,))
rows = cur.fetchall()
print(f"\napi_token rows for tenant: {len(rows)}")
for r in rows:
    # truncate token
    keys = list(r.keys())
    for k in keys:
        v = r[k]
        if isinstance(v, str) and len(v) > 60:
            r[k] = v[:20] + '...' + v[-10:]
    print(f"  {r}")

# user info
cur.execute("SELECT id, email, nickname FROM user")
print(f"\nUsers:")
for u in cur.fetchall():
    print(f"  {u}")

cur.close()
conn.close()

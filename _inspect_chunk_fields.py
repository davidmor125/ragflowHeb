"""Show ALL fields of one chunk to find where keywords are stored."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as ss
ss.init_settings()
from rag.nlp import search
from api.db.db_models import DB
DB.connect(reuse_if_open=True)

DOC_ID = 'f598a53c46e211f196f633ac796a3d7a'
KB = 'dc0091ca46e211f196f633ac796a3d7a'
TENANT = '2507563a42bd11f1a6bba9e87ac7a32c'

# Get all fields - empty list means all
res = ss.docStoreConn.search([], [], {'kb_id': KB, 'doc_id': DOC_ID}, [], {}, 0, 3,
                             [search.index_name(TENANT)], [KB])
items = list(ss.docStoreConn.get_fields(res, []).values())
print(f"Sample {len(items)} chunks:")
for i, p in enumerate(items):
    if isinstance(p, dict):
        print(f"\n--- Chunk #{i} ---")
        for k in sorted(p.keys()):
            v = p[k]
            if isinstance(v, str) and len(v) > 200:
                v = v[:200] + '...'
            print(f"  {k}: {v}")

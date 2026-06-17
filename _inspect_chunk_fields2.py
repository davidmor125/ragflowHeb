"""Show all fields of one chunk using ES directly."""
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

# Try with broader field list
fields = ['content_with_weight', 'important_kwd', 'important_tks', 'doc_type_kwd', 'kb_id', 'doc_id', 'docnm_kwd']
res = ss.docStoreConn.search(fields, [], {'kb_id': KB, 'doc_id': DOC_ID}, [], {}, 0, 5,
                             [search.index_name(TENANT)], [KB])
items_dict = ss.docStoreConn.get_fields(res, fields)
print(f"Got {len(items_dict)} chunks (dict)")

count_with_kwd = 0
for chunk_id, p in list(items_dict.items())[:3]:
    print(f"\n--- chunk_id={chunk_id} ---")
    if isinstance(p, dict):
        for k, v in p.items():
            if isinstance(v, str) and len(v) > 150:
                v_show = v[:150] + '...'
            else:
                v_show = v
            print(f"  {k} = {v_show}")
        if p.get('important_kwd'):
            count_with_kwd += 1

# Now count across all
res2 = ss.docStoreConn.search(['important_kwd'], [], {'kb_id': KB, 'doc_id': DOC_ID}, [], {}, 0, 200,
                              [search.index_name(TENANT)], [KB])
all_items = ss.docStoreConn.get_fields(res2, ['important_kwd'])
print(f"\nTotal chunks: {len(all_items)}")
n_with = 0
for cid, p in all_items.items():
    if isinstance(p, dict) and p.get('important_kwd'):
        n_with += 1
print(f"  with important_kwd: {n_with}")

"""Find a doc with at least one huge chunk (likely from a giant table)."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, Document
from rag.nlp import search as search_mod
DB.connect(reuse_if_open=True)

KB = 'dc0091ca46e211f196f633ac796a3d7a'
TENANT = '2507563a42bd11f1a6bba9e87ac7a32c'

docs = list(Document.select().where(Document.kb_id == KB))
print(f"Total docs: {len(docs)}")

big_docs = []
for d in docs:
    res = s.docStoreConn.search(['content_with_weight'], [], {'kb_id': KB, 'doc_id': d.id}, [], {}, 0, 200,
                                 [search_mod.index_name(TENANT)], [KB])
    items = list(s.docStoreConn.get_fields(res, ['content_with_weight']).values())
    sizes = [len((p.get('content_with_weight','') if isinstance(p, dict) else '')) for p in items]
    if sizes and max(sizes) > 16000:
        big_docs.append((d.id, d.name, max(sizes), len(sizes)))

big_docs.sort(key=lambda x: -x[2])
print(f"\nDocs with chunk > 16K: {len(big_docs)}")
for did, name, mx, n in big_docs[:10]:
    print(f"  {did}  {name[:50]:50}  max_chunk={mx}c  n_chunks={n}")

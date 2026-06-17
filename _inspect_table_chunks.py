"""Find chunks that are tables and check whether they have <th> headers."""
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

res = ss.docStoreConn.search(['content_with_weight','important_kwd','doc_type_kwd'], [], {'kb_id': KB, 'doc_id': DOC_ID}, [], {}, 0, 200,
                             [search.index_name(TENANT)], [KB])
items = list(ss.docStoreConn.get_fields(res, ['content_with_weight','important_kwd','doc_type_kwd']).values())
print(f"Total chunks: {len(items)}\n")

# Find table chunks - look for <table>
table_chunks = []
for i, p in enumerate(items):
    if isinstance(p, dict):
        text = p.get('content_with_weight','') or ''
        if '<table>' in text or '<tr>' in text:
            table_chunks.append((i, text, p.get('important_kwd'), p.get('doc_type_kwd')))

print(f"Chunks that contain <table> or <tr>: {len(table_chunks)}\n")

for idx, text, kwd, dtype in table_chunks[:5]:
    print(f"--- Chunk #{idx}  size={len(text)}  doc_type={dtype}  kwd={kwd} ---")
    # Show first 500c (header area)
    print("HEAD:")
    print(text[:600])
    print("...")
    print("TAIL:")
    print(text[-300:])
    print()

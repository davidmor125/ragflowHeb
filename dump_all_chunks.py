import sys
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from rag.utils.es_conn import ESConnection

es = ESConnection()
res = es.es.search(
    index='ragflow_2507563a42bd11f1a6bba9e87ac7a32c',
    body={
        'query': {'term': {'doc_id': '4166f44442cb11f19dd4bd85ecf60816'}},
        'size': 100,
        'sort': [{'page_num_int': 'asc'}],
        '_source': ['content_with_weight', 'doc_type_kwd', 'page_num_int']
    }
)
print(f"Total: {res['hits']['total']['value']}")
print()
for i, h in enumerate(res['hits']['hits']):
    src = h['_source']
    page = src.get('page_num_int')
    typ = src.get('doc_type_kwd', 'text')
    txt = src.get('content_with_weight', '')
    print(f"=== CHUNK {i+1} | page={page} | type={typ} | {len(txt)} chars ===")
    print(txt)
    print()

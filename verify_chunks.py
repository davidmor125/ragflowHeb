import sys
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from rag.utils.es_conn import ESConnection

es = ESConnection()
res = es.es.search(
    index='ragflow_2507563a42bd11f1a6bba9e87ac7a32c',
    body={
        'query': {'bool': {'must': [
            {'term': {'doc_id': '4166f44442cb11f19dd4bd85ecf60816'}},
            {'term': {'doc_type_kwd': 'image'}}
        ]}},
        'size': 30,
        '_source': ['content_with_weight', 'page_num_int']
    }
)

print(f"Total image chunks: {res['hits']['total']['value']}")
print()

for i, h in enumerate(res['hits']['hits']):
    src = h['_source']
    txt = src.get('content_with_weight', '')
    print(f"=== IMAGE CHUNK {i+1} (page {src.get('page_num_int')}) ===")
    print(txt[:800])
    print()

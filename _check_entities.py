"""Check whether GraphRAG entities + metadata exist for this doc."""
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

# 1) Check chunks for entity-like fields
print("=== Field summary across chunks ===")
res = ss.docStoreConn.search([], [], {'kb_id': KB, 'doc_id': DOC_ID}, [], {}, 0, 5,
                              [search.index_name(TENANT)], [KB])
# Use ES directly for better visibility
import requests
es_resp = requests.get(
    f'http://docker-es01-1:9200/ragflow_{TENANT}/_search?size=3',
    auth=('elastic', 'infini_rag_flow'),
    json={"query": {"term": {"doc_id": DOC_ID}}},
    timeout=10,
)
data = es_resp.json()
hits = data.get('hits', {}).get('hits', [])
print(f"\nFirst chunk fields:")
if hits:
    fields = set()
    for h in hits:
        fields.update(h.get('_source', {}).keys())
    for f in sorted(fields):
        print(f"  - {f}")

# 2) Check for entity-specific docs (graphrag stores entities as separate docs)
print("\n=== Entity/relation docs in this KB ===")
es_resp2 = requests.get(
    f'http://docker-es01-1:9200/ragflow_{TENANT}/_search?size=3',
    auth=('elastic', 'infini_rag_flow'),
    json={
        "query": {
            "bool": {
                "must": [
                    {"term": {"kb_id": KB}},
                    {"exists": {"field": "knowledge_graph_kwd"}}
                ]
            }
        }
    },
    timeout=10,
)
data2 = es_resp2.json()
total_kg = data2.get('hits', {}).get('total', {}).get('value', 0)
hits2 = data2.get('hits', {}).get('hits', [])
print(f"Total KG (entity/relation) docs in KB: {total_kg}")
for h in hits2[:3]:
    src = h.get('_source', {})
    print(f"\n  knowledge_graph_kwd: {src.get('knowledge_graph_kwd')}")
    print(f"  entity_kwd: {src.get('entity_kwd')}")
    print(f"  entity_type_kwd: {src.get('entity_type_kwd')}")
    cw = src.get('content_with_weight','')
    print(f"  content_with_weight (head 200): {cw[:200]}")

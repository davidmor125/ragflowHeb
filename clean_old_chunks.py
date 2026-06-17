import sys
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from rag.utils.es_conn import ESConnection

es = ESConnection()
DOC_ID = "4166f44442cb11f19dd4bd85ecf60816"
INDEX = "ragflow_2507563a42bd11f1a6bba9e87ac7a32c"

# Count before
res = es.es.count(index=INDEX, body={"query": {"term": {"doc_id": DOC_ID}}})
print(f"Total chunks before cleanup: {res['count']}")

# Cutoff: anything older than today's third parse (start at 00:46)
CUTOFF = "2026-04-29 14:55:00"

res = es.es.delete_by_query(
    index=INDEX,
    body={
        "query": {
            "bool": {
                "must": [{"term": {"doc_id": DOC_ID}}],
                "filter": [{"range": {"create_time": {"lt": CUTOFF}}}]
            }
        }
    },
    refresh=True
)
print(f"Deleted: {res.get('deleted', 0)} old chunks")

# Count after
res = es.es.count(index=INDEX, body={"query": {"term": {"doc_id": DOC_ID}}})
print(f"Total chunks after cleanup: {res['count']}")

import sys
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from rag.utils.es_conn import ESConnection
es = ESConnection()

KB_ID = "3e76c53642bf11f1a6bba9e87ac7a32c"
DOC_ID = "4166f44442cb11f19dd4bd85ecf60816"

# Get image-type chunks
res = es.es.search(
    index=f"ragflow_{KB_ID.split('_')[0] if '_' in KB_ID else '2507563a42bd11f1a6bba9e87ac7a32c'}",
    body={
        "query": {"bool": {"must": [
            {"term": {"doc_id": DOC_ID}}
        ]}},
        "size": 30,
        "_source": ["content_with_weight", "doc_type_kwd", "img_id", "page_num_int"]
    }
)
hits = res["hits"]["hits"]
print(f"Total chunks in this query: {len(hits)}")
print(f"Total in doc: {res['hits']['total']['value']}")
print()

image_chunks = [h for h in hits if h["_source"].get("doc_type_kwd") == "image"]
print(f"=== {len(image_chunks)} IMAGE CHUNKS ===")
for i, h in enumerate(image_chunks):
    src = h["_source"]
    text = src.get("content_with_weight", "")
    print(f"\n--- IMAGE CHUNK {i+1} ---")
    print(f"page: {src.get('page_num_int')}")
    print(f"img_id: {src.get('img_id', 'none')}")
    print(f"text ({len(text)} chars):")
    print(text[:1500])
    print("--- END ---")

text_chunks = [h for h in hits if h["_source"].get("doc_type_kwd") != "image"]
print(f"\n\n=== Sample of {min(3, len(text_chunks))} TEXT CHUNKS ===")
for i, h in enumerate(text_chunks[:3]):
    text = h["_source"].get("content_with_weight", "")
    print(f"\n--- TEXT CHUNK {i+1} ---")
    print(text[:600])

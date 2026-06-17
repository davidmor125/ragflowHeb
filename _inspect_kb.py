"""Check KB chunk size config + actual chunk size distribution."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB
from api.db.services.knowledgebase_service import KnowledgebaseService
from rag.nlp import search as search_mod
DB.connect(reuse_if_open=True)

KB = 'dc0091ca46e211f196f633ac796a3d7a'
TENANT = '2507563a42bd11f1a6bba9e87ac7a32c'

ok, kb = KnowledgebaseService.get_by_id(KB)
if not ok:
    print("KB not found")
    raise SystemExit(1)

print(f"KB: {kb.name}")
print(f"  parser_id: {kb.parser_id}")
print(f"  parser_config keys: {list((kb.parser_config or {}).keys())}")
print(f"  parser_config: {kb.parser_config}")
print()

# Sample 1000 chunks and show size distribution
res = s.docStoreConn.search(
    ['content_with_weight'], [], {'kb_id': KB}, [], {}, 0, 1000,
    [search_mod.index_name(TENANT)], [KB]
)
items = list(s.docStoreConn.get_fields(res, ['content_with_weight']).values())
sizes = [len((p.get('content_with_weight','') if isinstance(p, dict) else '')) for p in items]
sizes.sort()

print(f"Sampled {len(sizes)} chunks")
print(f"  min: {sizes[0]}c")
print(f"  median: {sizes[len(sizes)//2]}c")
print(f"  p90: {sizes[int(len(sizes)*0.9)]}c")
print(f"  p99: {sizes[int(len(sizes)*0.99)]}c")
print(f"  max: {sizes[-1]}c")
print()
print("Size buckets:")
buckets = [0, 500, 1000, 2000, 4000, 8000, 16000, 32000, 100000, 1000000]
for i in range(len(buckets)-1):
    lo, hi = buckets[i], buckets[i+1]
    n = sum(1 for s in sizes if lo <= s < hi)
    if n: print(f"  {lo:>6}c - {hi:>6}c: {n} chunks ({n*100//len(sizes)}%)")

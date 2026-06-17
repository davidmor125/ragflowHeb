"""Find a doc that:
1. Has a procedure number that appears in failed questions (kw_passed=False)
2. Has at least one big table chunk in original parse
"""
import sys, json, re
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as ss
ss.init_settings()
from api.db.db_models import DB, Document
from rag.nlp import search
DB.connect(reuse_if_open=True)

KB = 'dc0091ca46e211f196f633ac796a3d7a'
TENANT = '2507563a42bd11f1a6bba9e87ac7a32c'

with open('/ragflow/eval_llm_judged.json', encoding='utf-8') as f:
    eval_data = json.load(f)

# Failed questions
failed = [r for r in eval_data['results'] if not r['kw_passed']]
print(f"Total failed (kw=False): {len(failed)}")

# Group by procedure number
by_proc = {}
for r in failed:
    by_proc.setdefault(r['procedure'], []).append(r)
print(f"Procedures with failures: {len(by_proc)}")
print()

# For each failed procedure, find matching doc and check chunk sizes
docs = list(Document.select().where(Document.kb_id == KB))
docs_by_name = {d.name: d for d in docs}

candidates = []
for proc, q_list in by_proc.items():
    # Doc filename like 'טסט/<proc>.html'
    name = f"טסט/{proc}.html"
    doc = docs_by_name.get(name)
    if not doc:
        continue
    # Get current chunk sizes from ES
    res = ss.docStoreConn.search(['content_with_weight'], [], {'kb_id': KB, 'doc_id': doc.id}, [], {}, 0, 200,
                                   [search.index_name(TENANT)], [KB])
    items = ss.docStoreConn.get_fields(res, ['content_with_weight'])
    sizes = []
    for cid, p in items.items():
        if isinstance(p, dict):
            sizes.append(len(p.get('content_with_weight','') or ''))
    max_size = max(sizes) if sizes else 0
    candidates.append((proc, doc, max_size, len(sizes), q_list))

# Sort by max chunk size descending — biggest tables first
candidates.sort(key=lambda x: -x[2])

print(f"{'proc':>6} {'max':>7} {'chunks':>4}  questions failed")
print('-'*80)
for proc, doc, mx, n, q_list in candidates[:15]:
    print(f"{proc:>6} {mx:>7} {n:>4}  {len(q_list)} questions")
    for q in q_list[:2]:
        print(f"        n={q['n']:>3}: {q['question'][:60]}")

# Pick the top candidate with >16K max chunk and most questions
print()
top = next((c for c in candidates if c[2] > 16000), candidates[0] if candidates else None)
if top:
    proc, doc, mx, n, q_list = top
    print(f"\n>>> PICKED: proc={proc}  doc.id={doc.id}  max_chunk={mx}  questions={len(q_list)}")
    out = {
        'doc_id': doc.id,
        'doc_name': doc.name,
        'procedure': proc,
        'questions': [{'n': q['n'], 'question': q['question'], 'expected': q['expected']} for q in q_list],
    }
    with open('/ragflow/_target_doc.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

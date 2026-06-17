"""Verify that the proc=32904 chunks are correct:
- Sizes and counts
- Hebrew quality
- Table headers preserved (with new heuristic)
- Content covers all the key gold answer terms (ביטול, התכתבות, ויזה, ישראכרט, מקס)
- Show specific chunks that should answer the failed questions
"""
import sys, re
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as ss
ss.init_settings()
from rag.nlp import search
from api.db.db_models import DB, Document
DB.connect(reuse_if_open=True)

KB = 'dc0091ca46e211f196f633ac796a3d7a'
TENANT = '2507563a42bd11f1a6bba9e87ac7a32c'

doc = next(d for d in Document.select().where(Document.kb_id == KB) if d.name == 'טסט/32904.html')

res = ss.docStoreConn.search(['content_with_weight','important_kwd'], [], {'kb_id': KB, 'doc_id': doc.id}, [], {}, 0, 200,
                              [search.index_name(TENANT)], [KB])
items = list(ss.docStoreConn.get_fields(res, ['content_with_weight','important_kwd']).values())
print(f"Total chunks: {len(items)}")

# Size stats
sizes = [len(p.get('content_with_weight','') or '') for p in items if isinstance(p, dict)]
sizes.sort()
print(f"  size  min={sizes[0]} median={sizes[len(sizes)//2]} max={sizes[-1]}")
print(f"  >8K: {sum(1 for s in sizes if s>8000)}, >16K: {sum(1 for s in sizes if s>16000)}")

# Hebrew quality
heb = sum(sum(1 for c in p.get('content_with_weight','') or '' if 0x590<=ord(c)<=0x5ff) for p in items if isinstance(p, dict))
total_text = sum(sizes)
print(f"  Hebrew chars: {heb:,}/{total_text:,} ({heb*100//max(total_text,1)}%)")

# auto_keywords
with_kwd = sum(1 for p in items if isinstance(p, dict) and p.get('important_kwd'))
print(f"  auto_keywords: {with_kwd}/{len(items)}")

# Table chunks with headers
table_n = 0
table_with_th = 0
table_with_styled_first_row = 0
for p in items:
    if not isinstance(p, dict):
        continue
    text = p.get('content_with_weight','') or ''
    if '<table>' not in text and '<tr>' not in text:
        continue
    table_n += 1
    if '<th' in text:
        table_with_th += 1
    if 'background-color' in text and ('#0070c0' in text.lower() or '#1f4e78' in text.lower() or 'font-weight:bold' in text):
        table_with_styled_first_row += 1
print(f"  table chunks: {table_n}")
print(f"    with <th>: {table_with_th}")
print(f"    with styled first row: {table_with_styled_first_row}")

# Find the chunks that should answer our 4 failed questions
print("\n=== Chunks that mention key answer terms ===")
key_terms = ['ביטול כרטיס', 'התכתבות עם בנקאי', 'ויזה כאל', 'ישראכרט', 'מקס']
for term in key_terms:
    found = [(i, p) for i, p in enumerate(items) if isinstance(p, dict) and term in (p.get('content_with_weight','') or '')]
    print(f"\n'{term}' found in {len(found)} chunks")
    for idx, p in found[:2]:
        text = p.get('content_with_weight','') or ''
        # find term and show context
        pos = text.find(term)
        ctx = text[max(0,pos-100):pos+200].replace('\n',' ')
        print(f"  chunk #{idx}: ...{ctx}...")

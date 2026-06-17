"""Show chunk #11 of proc=32904 — supposed to contain the answer."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as ss
ss.init_settings()
from rag.nlp import search
from api.db.db_models import DB, Document
from bs4 import BeautifulSoup
DB.connect(reuse_if_open=True)

KB = 'dc0091ca46e211f196f633ac796a3d7a'
TENANT = '2507563a42bd11f1a6bba9e87ac7a32c'

doc = next(d for d in Document.select().where(Document.kb_id == KB) if d.name == 'טסט/32904.html')

res = ss.docStoreConn.search(['content_with_weight'], [], {'kb_id': KB, 'doc_id': doc.id}, [], {}, 0, 200,
                              [search.index_name(TENANT)], [KB])
items = list(ss.docStoreConn.get_fields(res, ['content_with_weight']).values())

# Find chunks that contain "התכתבות עם בנקאי" or "ביוזמת הלקוח"
for i, p in enumerate(items):
    if not isinstance(p, dict): continue
    text = p.get('content_with_weight','') or ''
    if 'התכתבות עם בנקאי' in text or 'ביוזמת לקוח' in text or 'ביוזמת הלקוח' in text:
        print(f"\n{'='*80}")
        print(f"CHUNK #{i}  size={len(text)}")
        print('='*80)
        # Strip HTML for readability
        soup = BeautifulSoup(text, 'html.parser')
        visible = soup.get_text()
        # Clean whitespace
        visible = '\n'.join(line.strip() for line in visible.split('\n') if line.strip())
        print(visible[:3000])

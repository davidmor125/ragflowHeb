"""Check what table HTML actually looks like in original docs."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as ss
ss.init_settings()
from rag.nlp import find_codec
from api.db.db_models import DB, Document
from bs4 import BeautifulSoup
DB.connect(reuse_if_open=True)

DOC_ID = 'f598a53c46e211f196f633ac796a3d7a'
doc = Document.get(Document.id == DOC_ID)
bin_data = ss.STORAGE_IMPL.get(doc.kb_id, doc.location)
encoding = find_codec(bin_data)
text = bin_data.decode(encoding, errors='ignore')
soup = BeautifulSoup(text, 'html5lib')

tables = soup.find_all('table')
print(f"Total tables: {len(tables)}")

# Check for <th>, <thead>, <caption>
n_thead = sum(1 for t in tables if t.find('thead'))
n_th = sum(1 for t in tables if t.find('th'))
n_caption = sum(1 for t in tables if t.find('caption'))
print(f"Tables with <thead>:  {n_thead}")
print(f"Tables with <th>:     {n_th}")
print(f"Tables with <caption>: {n_caption}")
print()

# Check first big table
print("=== First table sample (first 1500 chars) ===")
if tables:
    big = max(tables, key=lambda t: len(str(t)))
    print(f"size: {len(str(big))}")
    print(f"first row: {str(big.find('tr'))[:600]}")

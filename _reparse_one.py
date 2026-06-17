"""Re-parse a single document to verify the html_parser fix works."""
import sys, asyncio, os
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, Document, Task
from api.db.services.document_service import DocumentService
from rag.nlp import search as search_mod
DB.connect(reuse_if_open=True)

DOC_ID = 'f598a53c46e211f196f633ac796a3d7a'  # טסט/20064.html — biggest chunk 180K
KB = 'dc0091ca46e211f196f633ac796a3d7a'
TENANT = '2507563a42bd11f1a6bba9e87ac7a32c'

# Find the doc
docs = list(Document.select().where(Document.id == DOC_ID))
if not docs:
    print(f"Doc {DOC_ID} not found")
    raise SystemExit(1)

doc = docs[0]
print(f"Doc: {doc.name}")
print(f"  status: run={doc.run}  progress={doc.progress}")
print(f"  chunk_num={doc.chunk_num}  token_num={doc.token_num}")

# Trigger re-run by calling DocumentService.update_progress(or similar) to rerun
# Actually the simpler way: set run=2 (rerun) which the task_executor will pick up.
# But to verify the fix works, let's just call the parser directly.

import io
from rag.app import naive
from api.db.services.file2document_service import File2DocumentService
from common import settings as ss

# Read the file binary from storage
print(f"doc kb_id={doc.kb_id} location={doc.location}")
bin_data = ss.STORAGE_IMPL.get(doc.kb_id, doc.location)
print(f"binary size: {len(bin_data) if bin_data else 'NONE'}")

# Now call the html parser directly
from deepdoc.parser import HtmlParser
parser = HtmlParser()
sections = parser(doc.name, bin_data, 1024)
print(f"\nSections after parse: {len(sections)}")
sizes = [len(s) for s in sections]
sizes.sort()
print(f"  min: {sizes[0]}c  median: {sizes[len(sizes)//2]}c  max: {sizes[-1]}c")
print(f"  sections > 8K: {sum(1 for s in sizes if s > 8000)}")
print(f"  sections > 16K: {sum(1 for s in sizes if s > 16000)}")

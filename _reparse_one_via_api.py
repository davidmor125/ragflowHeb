"""Trigger parse on one specific document — same flow as UI 'parse' button.
Then wait for it to finish and report chunk stats.
"""
import sys, time
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as ss
ss.init_settings()
from api.db.db_models import DB, Document, Task
from api.db.services.document_service import DocumentService
from api.db.services.task_service import TaskService
from rag.nlp import search
DB.connect(reuse_if_open=True)

DOC_ID = 'f598a53c46e211f196f633ac796a3d7a'  # טסט/20064.html — biggest chunk 180K
KB = 'dc0091ca46e211f196f633ac796a3d7a'
TENANT = '2507563a42bd11f1a6bba9e87ac7a32c'

doc = Document.get(Document.id == DOC_ID)
print(f"Doc: {doc.name}")
print(f"  Before: chunks={doc.chunk_num} tokens={doc.token_num}")

# Same flow as document_app.run() with delete=True:
DocumentService.clear_chunk_num_when_rerun(DOC_ID)
DocumentService.update_by_id(DOC_ID, {"run": "1", "progress": 0, "progress_msg": "", "chunk_num": 0, "token_num": 0})
TaskService.filter_delete([Task.doc_id == DOC_ID])
if ss.docStoreConn.index_exist(search.index_name(TENANT), KB):
    ss.docStoreConn.delete({"doc_id": DOC_ID}, search.index_name(TENANT), KB)

doc_dict = doc.to_dict()
DocumentService.run(TENANT, doc_dict, {})
print(f"  Triggered. Polling for completion...")

# Poll
start = time.time()
while time.time() - start < 600:
    time.sleep(5)
    d = Document.get(Document.id == DOC_ID)
    elapsed = time.time() - start
    print(f"  [{elapsed:.0f}s] run={d.run} progress={d.progress:.2f} msg={(d.progress_msg or '')[-100:]}", flush=True)
    if str(d.run) in ("3", "4"):
        break

# Final stats
d = Document.get(Document.id == DOC_ID)
print(f"\nFinal: run={d.run} chunks={d.chunk_num} tokens={d.token_num}")

# Inspect chunks
res = ss.docStoreConn.search(['content_with_weight', 'important_kwd'], [], {'kb_id': KB, 'doc_id': DOC_ID}, [], {}, 0, 200,
                             [search.index_name(TENANT)], [KB])
items = list(ss.docStoreConn.get_fields(res, ['content_with_weight', 'important_kwd']).values())
print(f"\nChunks found: {len(items)}")
sizes = []
with_kwd = 0
for p in items:
    if isinstance(p, dict):
        text = p.get('content_with_weight','') or ''
        sizes.append(len(text))
        if p.get('important_kwd'):
            with_kwd += 1
sizes.sort()
if sizes:
    print(f"  min={sizes[0]}c  median={sizes[len(sizes)//2]}c  max={sizes[-1]}c")
    print(f"  >16K: {sum(1 for s in sizes if s > 16000)}")
    print(f"  >32K: {sum(1 for s in sizes if s > 32000)}")
    print(f"  with auto_keywords: {with_kwd}/{len(items)}")

# Show one with header preserved
print(f"\n--- Sample chunk (first 1500c) ---")
if items:
    sample = items[0]
    if isinstance(sample, dict):
        print(sample.get('content_with_weight','')[:1500])
        print(f"\nimportant_kwd: {sample.get('important_kwd')}")

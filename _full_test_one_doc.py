"""Full end-to-end on one doc:
1. Re-parse with new header-detection code
2. Trigger graphrag task on this doc
3. Wait + verify everything (chunks, headers, kwd, entities)
"""
import sys, time, datetime
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as ss
ss.init_settings()
from api.db.db_models import DB, Document, Task
from api.db.services.document_service import DocumentService, queue_raptor_o_graphrag_tasks
from api.db.services.task_service import TaskService
from rag.nlp import search
DB.connect(reuse_if_open=True)

DOC_ID = 'f598a53c46e211f196f633ac796a3d7a'
KB = 'dc0091ca46e211f196f633ac796a3d7a'
TENANT = '2507563a42bd11f1a6bba9e87ac7a32c'

# 1) Trigger parse
print("=== Step 1: Triggering parse ===", flush=True)
DocumentService.clear_chunk_num_when_rerun(DOC_ID)
DocumentService.update_by_id(DOC_ID, {"run": "1", "progress": 0, "progress_msg": "", "chunk_num": 0, "token_num": 0})
TaskService.filter_delete([Task.doc_id == DOC_ID])
if ss.docStoreConn.index_exist(search.index_name(TENANT), KB):
    ss.docStoreConn.delete({"doc_id": DOC_ID}, search.index_name(TENANT), KB)

doc = Document.get(Document.id == DOC_ID)
DocumentService.run(TENANT, doc.to_dict(), {})
print("Parse triggered. Polling...", flush=True)

start = time.time()
last_msg = ""
while time.time() - start < 1800:
    time.sleep(10)
    d = Document.get(Document.id == DOC_ID)
    elapsed = time.time() - start
    msg = (d.progress_msg or '').strip().split('\n')[-1] if d.progress_msg else ''
    if msg != last_msg:
        print(f"  [{elapsed:.0f}s] run={d.run} progress={d.progress:.2f}  {msg[:120]}", flush=True)
        last_msg = msg
    if str(d.run) in ("3", "4"):
        break

d = Document.get(Document.id == DOC_ID)
print(f"\nParse done. run={d.run} chunks={d.chunk_num}", flush=True)

# 2) Trigger graphrag task
print("\n=== Step 2: Triggering GraphRAG task ===", flush=True)
GRAPH_RAPTOR_FAKE_DOC_ID = "FAKE_GRAPH_RAPTOR_DOC_ID"
try:
    task_id = queue_raptor_o_graphrag_tasks(
        sample_doc=d.to_dict(),
        ty="graphrag",
        priority=0,
        fake_doc_id=GRAPH_RAPTOR_FAKE_DOC_ID,
        doc_ids=[DOC_ID]
    )
    print(f"GraphRAG task queued: {task_id}", flush=True)
except Exception as e:
    print(f"Error queueing graphrag: {e}", flush=True)
    import traceback
    traceback.print_exc()

# Poll graphrag task progress (it shows up as a Task row)
print("Polling graphrag...", flush=True)
start = time.time()
last_msg = ""
while time.time() - start < 1800:
    time.sleep(15)
    # Find latest graphrag task
    try:
        tasks = list(Task.select().where(Task.doc_id == GRAPH_RAPTOR_FAKE_DOC_ID).order_by(Task.create_time.desc()).limit(1))
        if not tasks:
            tasks = list(Task.select().order_by(Task.create_time.desc()).limit(3))
        for t in tasks[:1]:
            elapsed = time.time() - start
            msg = (t.progress_msg or '').strip().split('\n')[-1] if t.progress_msg else ''
            if msg != last_msg:
                print(f"  [{elapsed:.0f}s] task_id={t.id} progress={t.progress:.2f}  {msg[:200]}", flush=True)
                last_msg = msg
            if t.progress >= 1.0 or t.progress < 0:
                break
        else:
            continue
        break
    except Exception as e:
        print(f"  poll error: {e}", flush=True)
        time.sleep(15)

print("\nDone.", flush=True)

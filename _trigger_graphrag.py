"""Trigger GraphRAG with the CORRECT constant."""
import sys, time
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as ss
ss.init_settings()
from api.db.db_models import DB, Document, Task
from api.db.services.document_service import queue_raptor_o_graphrag_tasks
from api.db.services.task_service import GRAPH_RAPTOR_FAKE_DOC_ID
DB.connect(reuse_if_open=True)

DOC_ID = 'f598a53c46e211f196f633ac796a3d7a'
print(f"Real GRAPH_RAPTOR_FAKE_DOC_ID = {GRAPH_RAPTOR_FAKE_DOC_ID!r}", flush=True)

# Clean up any old broken graphrag tasks for this fake doc id
old = list(Task.select().where(Task.doc_id == GRAPH_RAPTOR_FAKE_DOC_ID))
for t in old:
    print(f"  cleaning up old task {t.id} (progress={t.progress})", flush=True)
Task.delete().where(Task.doc_id == GRAPH_RAPTOR_FAKE_DOC_ID).execute()

doc = Document.get(Document.id == DOC_ID)
task_id = queue_raptor_o_graphrag_tasks(
    sample_doc=doc.to_dict(),
    ty="graphrag",
    priority=0,
    fake_doc_id=GRAPH_RAPTOR_FAKE_DOC_ID,
    doc_ids=[DOC_ID]
)
print(f"queued task: {task_id}", flush=True)

# Poll
start = time.time()
last_msg = ""
while time.time() - start < 1800:
    time.sleep(15)
    t = Task.get_or_none(Task.id == task_id)
    if not t:
        print("Task disappeared from DB!", flush=True)
        break
    elapsed = time.time() - start
    msg = (t.progress_msg or '').strip().split('\n')[-1] if t.progress_msg else ''
    if msg != last_msg:
        print(f"  [{elapsed:.0f}s] progress={t.progress:.2f}  {msg[:200]}", flush=True)
        last_msg = msg
    if t.progress >= 1.0 or t.progress < 0:
        break

t = Task.get(Task.id == task_id)
print(f"\nFinal: progress={t.progress}", flush=True)
print(f"Last msg:\n{t.progress_msg}", flush=True)

"""Trigger re-parse on all docs in the KB.
Mimics what the /v1/document/run API does with delete=True:
  1. Clear existing chunks from doc store
  2. Delete tasks
  3. Set run=1 (RUNNING), progress=0
  4. Create new task
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as ss
ss.init_settings()
from api.db.db_models import DB, Document, Task
from api.db.services.document_service import DocumentService
from api.db.services.task_service import TaskService
from rag.nlp import search
DB.connect(reuse_if_open=True)

KB = 'dc0091ca46e211f196f633ac796a3d7a'
TENANT = '2507563a42bd11f1a6bba9e87ac7a32c'

docs = list(Document.select().where(Document.kb_id == KB))
print(f"Total docs in KB: {len(docs)}")

kb_table_num_map = {}
for i, doc in enumerate(docs, 1):
    try:
        # Reset state
        DocumentService.clear_chunk_num_when_rerun(doc.id)
        info = {"run": "1", "progress": 0, "progress_msg": "", "chunk_num": 0, "token_num": 0}
        DocumentService.update_by_id(doc.id, info)

        # Delete old tasks + chunks
        TaskService.filter_delete([Task.doc_id == doc.id])
        if ss.docStoreConn.index_exist(search.index_name(TENANT), doc.kb_id):
            ss.docStoreConn.delete({"doc_id": doc.id}, search.index_name(TENANT), doc.kb_id)

        # Schedule new task
        doc_dict = doc.to_dict()
        DocumentService.run(TENANT, doc_dict, kb_table_num_map)

        if i % 50 == 0:
            print(f"  scheduled {i}/{len(docs)}")
    except Exception as e:
        print(f"  ERROR on {doc.name}: {e}")

print(f"\nAll {len(docs)} docs scheduled. The task_executor will process them.")
print("Wait ~10-30 minutes. Monitor with: SELECT count(*) FROM task WHERE progress<1.0;")

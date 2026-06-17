import sys
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as common_settings
common_settings.init_settings()

from api.db.services.document_service import DocumentService
from api.db.services.task_service import queue_tasks
from api.db.services.file2document_service import File2DocumentService
from api.db.db_models import DB, Document, Task

DOC_ID = "4166f44442cb11f19dd4bd85ecf60816"

DB.connect(reuse_if_open=True)

DocumentService.update_by_id(DOC_ID, {
    "progress": 0.0,
    "progress_msg": "",
    "run": "1",
    "chunk_num": 0,
    "token_num": 0,
    "process_duration": 0.0,
})
print("Doc reset")

Task.delete().where(Task.doc_id == DOC_ID).execute()
print("Tasks cleared")

doc = Document.get(Document.id == DOC_ID)
bucket, name = File2DocumentService.get_storage_address(doc_id=DOC_ID)
queue_tasks(doc.to_dict(), bucket, name, 0)
print("Re-parse queued with gemma4:31b-cloud!")

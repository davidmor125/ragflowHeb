"""Reset hozrim_poc to use basic parsing (no pipeline) so we can run
Agentic RAG on its 20 files."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as s
s.init_settings()
from api.db.db_models import DB, Knowledgebase, Document, Task
from api.db.services.document_service import DocumentService
DB.connect(reuse_if_open=True)

KB_ID = '928f816a487a11f1a37a31aeaf1accf8'  # hozrim_poc

kb = Knowledgebase.get(Knowledgebase.id == KB_ID)
print(f"KB: {kb.name}  current pipeline_id: {kb.pipeline_id}")

# Detach pipeline from KB
kb.pipeline_id = None
kb.save()

# Detach pipeline from each document
docs = list(Document.select().where(Document.kb_id == KB_ID))
for d in docs:
    Document.update(pipeline_id='',
                    progress=0, progress_msg='',
                    chunk_num=0, run=0, status='1').where(Document.id == d.id).execute()
print(f"Detached pipeline from {len(docs)} docs")

# Cancel existing tasks
n = (Task.delete()
     .where(Task.doc_id.in_([d.id for d in docs]))
     .execute())
print(f"Removed {n} tasks")

# Re-queue with naive parser (no extractors)
queued = 0
for d in Document.select().where(Document.kb_id == KB_ID):
    DocumentService.run(getattr(d, 'tenant_id', None), d.to_dict(), {})
    queued += 1
print(f"Queued {queued} docs for basic parse")

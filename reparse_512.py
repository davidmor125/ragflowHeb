"""Set chunk_token_num=512 on hozrim_poc and re-parse all 20 docs."""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as s
s.init_settings()
from api.db.db_models import DB, Knowledgebase, Document, Task
from api.db.services.document_service import DocumentService
DB.connect(reuse_if_open=True)

KB_ID = '928f816a487a11f1a37a31aeaf1accf8'

kb = Knowledgebase.get(Knowledgebase.id == KB_ID)
cfg = dict(kb.parser_config)
print(f'BEFORE chunk_token_num: {cfg.get("chunk_token_num")}')
cfg['chunk_token_num'] = 512
kb.parser_config = cfg
kb.save()

kb2 = Knowledgebase.get(Knowledgebase.id == KB_ID)
print(f'AFTER  chunk_token_num: {kb2.parser_config.get("chunk_token_num")}')

# Cancel pending tasks for these docs and reset
docs = list(Document.select().where(Document.kb_id == KB_ID))
n = (Task.delete()
     .where(Task.doc_id.in_([d.id for d in docs]), Task.progress < 1.0)
     .execute())
print(f'\nRemoved {n} pending tasks')

for d in docs:
    Document.update(progress=0, progress_msg='', chunk_num=0, run=0, status='1').where(Document.id == d.id).execute()
print(f'Reset progress on {len(docs)} docs')

queued = 0
for d in Document.select().where(Document.kb_id == KB_ID):
    DocumentService.run(getattr(d, 'tenant_id', None), d.to_dict(), {})
    queued += 1
print(f'Queued {queued} docs for re-parse')

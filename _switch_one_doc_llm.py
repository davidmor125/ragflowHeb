"""Switch the LLM for ONE doc to gpt-oss:20b@Ollama (local), then trigger parse."""
import sys, time, datetime
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as ss
ss.init_settings()
from api.db.db_models import DB, Document, Task
from api.db.services.document_service import DocumentService
from api.db.services.task_service import TaskService
from rag.nlp import search
DB.connect(reuse_if_open=True)

DOC_ID = 'f598a53c46e211f196f633ac796a3d7a'  # טסט/20064.html
KB = 'dc0091ca46e211f196f633ac796a3d7a'
TENANT = '2507563a42bd11f1a6bba9e87ac7a32c'
NEW_LLM = 'gpt-oss:20b@Ollama'

# 1) Switch LLM in this doc only
doc = Document.get(Document.id == DOC_ID)
cfg = dict(doc.parser_config or {})
old = cfg.get('llm_id')
cfg['llm_id'] = NEW_LLM
Document.update(parser_config=cfg).where(Document.id == DOC_ID).execute()
print(f"Doc parser_config.llm_id: {old} -> {NEW_LLM}")

# 2) Trigger parse
DocumentService.clear_chunk_num_when_rerun(DOC_ID)
DocumentService.update_by_id(DOC_ID, {"run": "1", "progress": 0, "progress_msg": "", "chunk_num": 0, "token_num": 0})
TaskService.filter_delete([Task.doc_id == DOC_ID])
if ss.docStoreConn.index_exist(search.index_name(TENANT), KB):
    ss.docStoreConn.delete({"doc_id": DOC_ID}, search.index_name(TENANT), KB)

doc = Document.get(Document.id == DOC_ID)
DocumentService.run(TENANT, doc.to_dict(), {})
print("Triggered. Polling...")

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
print(f"\nFinal: run={d.run} chunks={d.chunk_num} tokens={d.token_num}")
print(f"\nFull progress_msg:")
print(d.progress_msg)

"""Switch parser_config llm_id from gpt-oss:120b-cloud to gpt-oss:20b LOCAL,
both at KB level and at all 646 doc levels.
"""
import sys, datetime
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, Document
from api.db.services.knowledgebase_service import KnowledgebaseService
DB.connect(reuse_if_open=True)

KB = 'dc0091ca46e211f196f633ac796a3d7a'
NEW_LLM = 'gpt-oss:20b@Ollama'

# 1. KB-level
ok, kb = KnowledgebaseService.get_by_id(KB)
cfg = dict(kb.parser_config or {})
old = cfg.get('llm_id')
cfg['llm_id'] = NEW_LLM
# Also propagate into raptor sub-config which has its own LLM ref
if 'raptor' in cfg:
    cfg['raptor'] = dict(cfg['raptor'])
kb.parser_config = cfg
kb.update_time = int(datetime.datetime.now().timestamp() * 1000)
kb.update_date = datetime.datetime.now()
kb.save()
print(f"KB.parser_config.llm_id: {old} -> {NEW_LLM}")

# 2. Doc-level — sync all 646
docs = list(Document.select().where(Document.kb_id == KB))
print(f"Updating {len(docs)} docs...")
n = 0
for doc in docs:
    dcfg = dict(doc.parser_config or {})
    if dcfg.get('llm_id') != NEW_LLM:
        dcfg['llm_id'] = NEW_LLM
        Document.update(parser_config=dcfg).where(Document.id == doc.id).execute()
        n += 1
print(f"  updated {n} docs (others already had {NEW_LLM})")

# Verify on test doc
doc = Document.get(Document.id == 'f598a53c46e211f196f633ac796a3d7a')
print(f"\nVerify f598a... parser_config.llm_id = {doc.parser_config.get('llm_id')}")

"""Sync all docs in the KB to use the KB-level parser_config.
The Task uses Document.parser_config (not Knowledgebase.parser_config),
so changes to KB config don't affect existing docs unless we propagate.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, Document
from api.db.services.knowledgebase_service import KnowledgebaseService
DB.connect(reuse_if_open=True)

KB = 'dc0091ca46e211f196f633ac796a3d7a'
ok, kb = KnowledgebaseService.get_by_id(KB)
print(f"KB.parser_config keys: {list(kb.parser_config.keys())}")
print(f"KB.parser_config.auto_keywords = {kb.parser_config.get('auto_keywords')}")
print(f"KB.parser_config.graphrag.entity_types = {kb.parser_config.get('graphrag', {}).get('entity_types')}")
print()

docs = list(Document.select().where(Document.kb_id == KB))
print(f"Updating {len(docs)} docs...")
n = 0
for doc in docs:
    cfg = dict(doc.parser_config or {})
    cfg['auto_keywords'] = kb.parser_config.get('auto_keywords', 0)
    cfg['auto_questions'] = kb.parser_config.get('auto_questions', 0)
    if 'graphrag' in kb.parser_config:
        cfg['graphrag'] = kb.parser_config['graphrag']
    Document.update(parser_config=cfg).where(Document.id == doc.id).execute()
    n += 1
print(f"Updated {n} docs")

# Verify on the test doc
doc = Document.get(Document.id == 'f598a53c46e211f196f633ac796a3d7a')
print(f"\nVerify f598a... parser_config:")
print(f"  auto_keywords = {doc.parser_config.get('auto_keywords')}")
print(f"  graphrag.entity_types = {doc.parser_config.get('graphrag', {}).get('entity_types')}")

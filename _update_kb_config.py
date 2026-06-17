"""Update KB config:
B. auto_keywords = 3  (extract 3 keywords per chunk via LLM)
C. entity_types tuned for Hebrew banking procedures
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB
from api.db.services.knowledgebase_service import KnowledgebaseService
DB.connect(reuse_if_open=True)

KB = 'dc0091ca46e211f196f633ac796a3d7a'

ok, kb = KnowledgebaseService.get_by_id(KB)
if not ok:
    print("KB not found")
    raise SystemExit(1)

cfg = dict(kb.parser_config or {})

print("BEFORE:")
print(f"  auto_keywords  = {cfg.get('auto_keywords')}")
print(f"  auto_questions = {cfg.get('auto_questions')}")
print(f"  graphrag.entity_types = {cfg.get('graphrag', {}).get('entity_types')}")
print()

# B: enable keyword extraction
cfg['auto_keywords'] = 3

# C: entity types tuned for Hebrew banking procedures
graphrag = dict(cfg.get('graphrag', {}))
graphrag['entity_types'] = [
    "procedure",        # נוהל
    "form",             # טופס
    "account_type",     # סוג חשבון (פרטי, עסקי, צעיר, מקוון)
    "transaction",      # פעולה / סוג פעולה
    "system",           # מערכת (מאיה, תנופה, סניפית)
    "regulation",       # רגולציה / חוק
    "amount",           # סכום / סף
    "rate",             # שיעור (ריבית, עמלה)
    "person",           # תפקיד (פקיד מורשה, מנהל)
    "organization",     # ארגון (בנק, חברה)
]
cfg['graphrag'] = graphrag

print("AFTER:")
print(f"  auto_keywords  = {cfg.get('auto_keywords')}")
print(f"  auto_questions = {cfg.get('auto_questions')}")
print(f"  graphrag.entity_types = {cfg['graphrag']['entity_types']}")
print()

# Save
import datetime
kb.parser_config = cfg
kb.update_time = int(datetime.datetime.now().timestamp() * 1000)
kb.update_date = datetime.datetime.now()
kb.save()
print("KB config updated")

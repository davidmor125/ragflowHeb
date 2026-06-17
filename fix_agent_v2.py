"""Apply fix: switch LLM to gpt-oss:120b-cloud, update prompt, agent + retrieval params,
re-parse with chunk_token_num=512 (and the existing sentence-boundary delimiter)."""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas, Knowledgebase, Document, Task
from api.db.services.document_service import DocumentService
DB.connect(reuse_if_open=True)

AGENT_ID = '54e45b8048a011f18e412992204f7aa3'
KB_ID    = '928f816a487a11f1a37a31aeaf1accf8'
NEW_LLM  = 'gpt-oss:120b-cloud@Ollama'

NEW_SYS_PROMPT = """אתה עוזר בנקאי חכם המתבסס על נהלים פנימיים.

כללי עבודה:
1. אם אין לך מספיק מידע — השתמש בכלי search_my_dateset_0.
2. אם כבר קיבלת מידע רלוונטי מהכלי — אל תקרא שוב לכלי.
3. השתמש בכלי לכל היותר פעם אחת, אלא אם חסר מידע קריטי.
4. לאחר קבלת מידע — עבור מיד לכתיבת תשובה מלאה למשתמש.
5. אל תיכנס ללולאה של חיפושים חוזרים.

מטרה: לתת תשובה מדויקת, מלאה וברורה בעברית.

מילון מונחים בנקאיים:
- פל"ת = פיקדון ללא תנועה
- מו"ח = מורשה חתימה
- ני"ע = ניירות ערך
- מט"ח = מטבע חוץ; מט"י = מטבע ישראלי
- ס.פ. = סוג פעולה במערכת הסניפית
- תמנון+ = מערכת איסור הלבנת הון
- תנופה = מערכת ניהול בקשות משכנתא
- חשבון מקוון = חשבון שנפתח באפליקציה
- ריכוז תעריפוני = נוהל 25813 — מקור לכל שאלת עמלה

פורמט תשובה:
- בעברית בלבד, ישירה, בלי הקדמות.
- כלול מספרים, מועדים, טפסים, ותהליכים מהמסמכים.
- ציין בסוף שם קובץ הנוהל.
- אם המידע באמת לא נמצא: "המידע אינו קיים בנהלים שצורפו"."""

# Resolve tenant_llm_id for the new LLM
from api.db.joint_services.tenant_model_service import get_model_config_by_type_and_name
from common.constants import LLMType
canvas = UserCanvas.get(UserCanvas.id == AGENT_ID)
tenant_id = canvas.user_id
mc = get_model_config_by_type_and_name(tenant_id, LLMType.CHAT, NEW_LLM)
new_tenant_llm_id = mc.get('id')
print(f"gpt-oss:120b-cloud tenant_llm_id: {new_tenant_llm_id}  is_tools: {mc.get('is_tools')}")

# --- Update Agent canvas ---
dsl = json.loads(json.dumps(canvas.dsl))

for cid, comp in dsl['components'].items():
    if comp['obj']['component_name'] == 'Agent':
        comp['obj']['params']['llm_id']        = NEW_LLM
        comp['obj']['params']['tenant_llm_id'] = new_tenant_llm_id
        comp['obj']['params']['sys_prompt']    = NEW_SYS_PROMPT
        comp['obj']['params']['max_rounds']    = 5
        comp['obj']['params']['max_tokens']    = 2048
        comp['obj']['params']['maxTokensEnabled'] = True
        comp['obj']['params']['temperature']   = 0.1
        for tool in comp['obj']['params'].get('tools', []):
            if tool.get('component_name') == 'Retrieval':
                tool['params']['top_n']                = 3
                tool['params']['top_k']                = 100
                tool['params']['similarity_threshold'] = 0.2

for n in dsl.get('graph', {}).get('nodes', []):
    if n.get('data', {}).get('label') == 'Agent':
        n['data']['form']['llm_id']     = NEW_LLM
        n['data']['form']['sys_prompt'] = NEW_SYS_PROMPT
        n['data']['form']['max_rounds'] = 5
        n['data']['form']['max_tokens'] = 2048
        n['data']['form']['temperature'] = 0.1
        for tool in n['data']['form'].get('tools', []):
            if tool.get('component_name') == 'Retrieval':
                tool['params']['top_n']                = 3
                tool['params']['top_k']                = 100
                tool['params']['similarity_threshold'] = 0.2

canvas.dsl = dsl
canvas.save()

# --- Update KB chunking ---
kb = Knowledgebase.get(Knowledgebase.id == KB_ID)
cfg = dict(kb.parser_config)
old_chunk = cfg.get("chunk_token_num")
old_delim = cfg.get("delimiter")
cfg['chunk_token_num'] = 512
# Keep the existing delimiter — it splits on sentence boundaries (.!? etc.)
# so the parser won't cut mid-sentence.
cfg['delimiter'] = "\n!?.;。；！？"
kb.parser_config = cfg
kb.save()

print()
print("=" * 60)
print(f"✓ LLM:                 {NEW_LLM}")
print(f"✓ System prompt:       {len(NEW_SYS_PROMPT)} chars")
print(f"✓ Agent params:        max_rounds=5, max_tokens=2048, temperature=0.1")
print(f"✓ Retrieval params:    top_n=3, top_k=100, similarity_threshold=0.2")
print(f"✓ Chunking:            {old_chunk} → 512 tokens (sentence-boundary delimiter preserved)")
print()

# --- Re-parse all 20 docs ---
docs = list(Document.select().where(Document.kb_id == KB_ID))
Task.delete().where(Task.doc_id.in_([d.id for d in docs])).execute()
for d in docs:
    Document.update(progress=0, progress_msg='', chunk_num=0, run=0, status='1', token_num=0).where(Document.id == d.id).execute()
queued = 0
for d in Document.select().where(Document.kb_id == KB_ID):
    DocumentService.run(getattr(d, 'tenant_id', None), d.to_dict(), {})
    queued += 1
print(f"Queued {queued} docs for re-parse with chunk_token_num=512")

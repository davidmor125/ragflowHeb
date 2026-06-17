"""Build Agentic RAG v2 — Pipeline architecture matching the user's diagram.

Flow:
   Begin
     ↓
   LLM: Query Rewriter (expands banking abbrev, refines question)
     ↓
   Retrieval (deterministic node, top_n=15)
     ↓
   LLM: Answer Generator (NO tools, just Hebrew answer based on chunks)
     ↓
   Message

Key design choices:
- Query Rewriter is a separate node (not the Agent doing it implicitly)
- Retrieval is deterministic (always called exactly once per pass)
- Answer Generator has NO tools → cannot loop, must answer
- gemma4:31b-cloud throughout (excellent Hebrew, no reasoning leak)
"""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
from common.misc_utils import get_uuid
DB.connect(reuse_if_open=True)

KB_HOZRIM = 'dc0091ca46e211f196f633ac796a3d7a'
LLM = 'gemma4:31b-cloud@Ollama'
RERANK = 'BAAI/bge-reranker-v2-m3@HuggingFace'

# Pull a tenant_id from an existing canvas
src_canvas = UserCanvas.get(UserCanvas.id == '54e45b8048a011f18e412992204f7aa3')
TENANT = src_canvas.user_id

# Generate component IDs
REWRITER_ID = "Agent:" + get_uuid()[:14]
RETRIEVAL_ID = "Retrieval:" + get_uuid()[:14]
ANSWER_ID = "Agent:" + get_uuid()[:14]
MSG_ID = "Message:" + get_uuid()[:14]

REWRITER_PROMPT = """אתה כותב מחדש שאלות עבור מערכת חיפוש בנהלי בנק.

קח את שאלת המשתמש והפק שאילתת חיפוש מדויקת בעברית.

הוראות:
1. שמור על המשמעות המקורית של השאלה.
2. הרחב ראשי תיבות: פל"ת = פיקדון ללא תנועה, מו"ח = מורשה חתימה, ני"ע = ניירות ערך, מט"ח = מטבע חוץ, ס.פ. = סוג פעולה, גלא"ש = גורם לאישור אשראי שיורי, תמנון+ = מערכת איסור הלבנת הון, תנופה = מערכת ניהול בקשות משכנתא, חשבון מקוון = חשבון שנפתח באפליקציה, הו"ק = הוראת קבע, ריכוז תעריפוני = נוהל 25813, מאיה = מערכת סניפית, דולב = מערכת דוחות.
3. הוסף מילות מפתח רלוונטיות אם השאלה כללית.
4. אל תוסיף הקשר שאינו בשאלה.
5. תפלט שורה אחת בלבד — שאילתת החיפוש החדשה. בלי הסברים, בלי thinking.

דוגמה:
שאלה: "כמה כסף ניתן להפקיד בחשבון מקוון יחיד?"
פלט: "תקבולים מקסימליים בחשבון מקוון יחיד הפקדה תקרה חודשית"
"""

ANSWER_PROMPT = """אתה עוזר בנקאי. ענה על השאלה רק על בסיס הנהלים שצורפו.

הוראות:
1. ענה בעברית בלבד, ישירה, בלי thinking ובלי הקדמות.
2. כלול את כל הפרטים הרלוונטיים: מספרים, סכומים, מועדים, שמות טפסים, סעיפים בנהלים.
3. ציטוטים מדויקים — אסור להמציא או לנסח מחדש מספרים וסכומים.
4. ציין בסוף שם קובץ הנוהל.
5. אם המידע באמת לא נמצא בנהלים: "המידע אינו קיים בנהלים שצורפו".

מילון מונחים:
- פל"ת = פיקדון ללא תנועה
- מו"ח = מורשה חתימה
- ני"ע = ניירות ערך
- מט"ח = מטבע חוץ
- ס.פ. / ס"פ = סוג פעולה (ס"פ 172 = העברות מט"ח, ס"פ 111 = הוראות קבע, ס"פ 940 = פנקסי שיקים)
- תמנון+ = מערכת איסור הלבנת הון
- תנופה = מערכת ניהול בקשות משכנתא
- מאיה = מערכת סניפית מרכזית
- ריכוז תעריפוני = נוהל 25813 (לכל שאלת עמלה)"""

dsl = {
    "components": {
        "begin": {
            "downstream": [REWRITER_ID],
            "obj": {
                "component_name": "Begin",
                "params": {
                    "prologue": "שלום! אני עוזר הבנק. שאל אותי על נהלים והנחיות עבודה.",
                    "inputs": {}
                }
            },
            "upstream": []
        },
        REWRITER_ID: {
            "downstream": [RETRIEVAL_ID],
            "obj": {
                "component_name": "Agent",
                "params": {
                    "llm_id": LLM,
                    "max_rounds": 1,
                    "max_tokens": 256,
                    "maxTokensEnabled": True,
                    "temperature": 0.0,
                    "temperatureEnabled": True,
                    "sys_prompt": REWRITER_PROMPT,
                    "prompts": [{"role": "user", "content": "שאלה: {sys.query}\n\nפלט (שאילתת חיפוש בלבד):"}],
                    "outputs": {"content": {"type": "string", "value": ""}},
                    "tools": [],
                    "cite": False,
                    "max_retries": 2,
                    "delay_after_error": 1,
                    "exception_method": None,
                    "exception_default_value": "",
                    "exception_goto": [],
                    "exception_comment": "",
                    "frequencyPenaltyEnabled": False,
                    "frequency_penalty": 0.0,
                    "presencePenaltyEnabled": False,
                    "presence_penalty": 0.0,
                    "topPEnabled": False,
                    "top_p": 1.0,
                    "mcp": [],
                    "message_history_window_size": 0,
                    "user_prompt": "",
                    "visual_files_var": ""
                }
            },
            "upstream": ["begin"]
        },
        RETRIEVAL_ID: {
            "downstream": [ANSWER_ID],
            "obj": {
                "component_name": "Retrieval",
                "params": {
                    "kb_ids": [KB_HOZRIM],
                    "dataset_ids": [KB_HOZRIM],
                    "rerank_id": RERANK,
                    "top_n": 15,
                    "top_k": 1024,
                    "similarity_threshold": 0.1,
                    "keywords_similarity_weight": 0.7,
                    "use_kg": False,
                    "cross_languages": [],
                    "empty_response": "",
                    "outputs": {"formalized_content": {"type": "string", "value": ""}},
                    "query": f"{{{REWRITER_ID}@content}}"
                }
            },
            "upstream": [REWRITER_ID]
        },
        ANSWER_ID: {
            "downstream": [MSG_ID],
            "obj": {
                "component_name": "Agent",
                "params": {
                    "llm_id": LLM,
                    "max_rounds": 1,
                    "max_tokens": 2048,
                    "maxTokensEnabled": True,
                    "temperature": 0.1,
                    "temperatureEnabled": True,
                    "sys_prompt": ANSWER_PROMPT,
                    "prompts": [{
                        "role": "user",
                        "content": "שאלה: {sys.query}\n\nנהלים רלוונטיים:\n{" + RETRIEVAL_ID + "@formalized_content}\n\nתשובה (בעברית בלבד):"
                    }],
                    "outputs": {"content": {"type": "string", "value": ""}},
                    "tools": [],
                    "cite": False,
                    "max_retries": 2,
                    "delay_after_error": 1,
                    "exception_method": None,
                    "exception_default_value": "",
                    "exception_goto": [],
                    "exception_comment": "",
                    "frequencyPenaltyEnabled": False,
                    "frequency_penalty": 0.0,
                    "presencePenaltyEnabled": False,
                    "presence_penalty": 0.0,
                    "topPEnabled": False,
                    "top_p": 1.0,
                    "mcp": [],
                    "message_history_window_size": 0,
                    "user_prompt": "",
                    "visual_files_var": ""
                }
            },
            "upstream": [RETRIEVAL_ID]
        },
        MSG_ID: {
            "downstream": [],
            "obj": {
                "component_name": "Message",
                "params": {"content": [f"{{{ANSWER_ID}@content}}"]}
            },
            "upstream": [ANSWER_ID]
        }
    },
    "globals": {
        "sys.history": [],
        "sys.query": "",
        "sys.user_id": "",
        "sys.conversation_turns": 0,
        "sys.files": [],
        "sys.date": ""
    },
    "graph": {
        "nodes": [
            {"id": "begin", "type": "beginNode", "position": {"x": 50, "y": 200},
             "measured": {"height": 50, "width": 200},
             "sourcePosition": "right", "targetPosition": "left",
             "data": {"label": "Begin", "name": "Begin"}},
            {"id": REWRITER_ID, "type": "agentNode", "position": {"x": 280, "y": 200},
             "measured": {"height": 80, "width": 200},
             "sourcePosition": "right", "targetPosition": "left",
             "data": {"label": "Agent", "name": "Query_Rewriter",
                      "form": {"llm_id": LLM, "sys_prompt": REWRITER_PROMPT, "max_tokens": 256, "temperature": 0.0, "tools": []}}},
            {"id": RETRIEVAL_ID, "type": "retrievalNode", "position": {"x": 510, "y": 200},
             "measured": {"height": 80, "width": 200},
             "sourcePosition": "right", "targetPosition": "left",
             "data": {"label": "Retrieval", "name": "Retrieval",
                      "form": {"kb_ids": [KB_HOZRIM], "rerank_id": RERANK, "top_n": 15, "similarity_threshold": 0.1}}},
            {"id": ANSWER_ID, "type": "agentNode", "position": {"x": 740, "y": 200},
             "measured": {"height": 80, "width": 200},
             "sourcePosition": "right", "targetPosition": "left",
             "data": {"label": "Agent", "name": "Answer_Generator",
                      "form": {"llm_id": LLM, "sys_prompt": ANSWER_PROMPT, "max_tokens": 2048, "temperature": 0.1, "tools": []}}},
            {"id": MSG_ID, "type": "messageNode", "position": {"x": 970, "y": 200},
             "measured": {"height": 50, "width": 200},
             "sourcePosition": "right", "targetPosition": "left",
             "data": {"label": "Message", "name": "Reply",
                      "form": {"content": [f"{{{ANSWER_ID}@content}}"]}}}
        ],
        "edges": [
            {"id": f"e1", "source": "begin", "sourceHandle": "start", "target": REWRITER_ID, "targetHandle": "end"},
            {"id": f"e2", "source": REWRITER_ID, "sourceHandle": "start", "target": RETRIEVAL_ID, "targetHandle": "end"},
            {"id": f"e3", "source": RETRIEVAL_ID, "sourceHandle": "start", "target": ANSWER_ID, "targetHandle": "end"},
            {"id": f"e4", "source": ANSWER_ID, "sourceHandle": "start", "target": MSG_ID, "targetHandle": "end"}
        ]
    },
    "history": [],
    "messages": [],
    "path": [],
    "retrieval": [],
    "variables": []
}

new_id = get_uuid()
UserCanvas.insert({
    'id': new_id,
    'avatar': src_canvas.avatar,
    'user_id': TENANT,
    'title': 'banking_agentic_rag_v2',
    'description': 'Agentic RAG v2 — Pipeline architecture: Query Rewriter → Retrieval → Answer Generator. '
                   'Each node has a single responsibility. No tool-calling loops. Hebrew banking domain.',
    'canvas_type': 'agent_canvas',
    'dsl': dsl,
    'permission': src_canvas.permission,
}).execute()

print(f"Created agent canvas:")
print(f"  id:    {new_id}")
print(f"  title: banking_agentic_rag_v2")
print(f"  flow:  Begin → Query_Rewriter (gemma4) → Retrieval (top_n=15) → Answer_Generator (gemma4, no tools) → Reply")
print()
print(f"Save this id for the eval script: {new_id}")

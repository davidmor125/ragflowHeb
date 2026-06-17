"""Build Agentic RAG v3 — Full pattern with self-check loop.

Flow (matching the user's diagram):
   Begin
     ↓
   Query_Rewriter (LLM, 1st pass: keeps original)
     ↓
   Retrieval (uses sys.query — original question)
     ↓
   Answer_Generator (LLM, no tools, generates answer)
     ↓
   Self_Check (Categorize: PASS/RETRY)
     ├─ PASS → Final_Reply (Message)
     └─ RETRY → Retrieval_v2 (uses Rewriter output as fallback) → Answer_v2 → Final_Reply

This way:
- Original well-phrased questions go via direct path
- Failed answers get a second chance via the rewriter's enriched query
- No infinite loops (max 2 retrieval attempts total)
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

src = UserCanvas.get(UserCanvas.id == '54e45b8048a011f18e412992204f7aa3')
TENANT = src.user_id

# Component IDs
REWRITER_ID  = "Agent:" + get_uuid()[:14]
RETRIEVAL1_ID = "Retrieval:" + get_uuid()[:14]
ANSWER1_ID   = "Agent:" + get_uuid()[:14]
SELFCHECK_ID = "Categorize:" + get_uuid()[:14]
RETRIEVAL2_ID = "Retrieval:" + get_uuid()[:14]
ANSWER2_ID   = "Agent:" + get_uuid()[:14]
MSG1_ID      = "Message:" + get_uuid()[:14]
MSG2_ID      = "Message:" + get_uuid()[:14]

REWRITER_PROMPT = """אתה מסייע למערכת חיפוש בנהלי בנק. הרחב את שאלת המשתמש כדי לעזור לחיפוש.

חוקים:
1. שמור על השאלה המקורית במלואה.
2. הוסף בסוגריים פירוש לראשי תיבות וביטויי מפתח.
3. הוסף 1-2 מילים נרדפות אם השאלה כללית.
4. תפלט שורה אחת בלבד, ללא הסברים.

מילון: פל"ת = פיקדון ללא תנועה | מו"ח = מורשה חתימה | ני"ע = ניירות ערך | מט"ח = מטבע חוץ | ס.פ./ס"פ = סוג פעולה | תמנון+ = איסור הלבנת הון | תנופה = ניהול בקשות משכנתא | מאיה = מערכת סניפית | ריכוז תעריפוני = נוהל 25813
"""

ANSWER_PROMPT = """אתה עוזר בנקאי. ענה בעברית בלבד על בסיס הנהלים שצורפו לך.

הוראות:
1. קרא את כל הנהלים שצורפו ומצא את המידע הרלוונטי.
2. תשובה ישירה ומפורטת בעברית. ללא thinking באנגלית, ללא הקדמות.
3. צטט מספרים, סכומים, מועדים, ושמות טפסים בדיוק מהנוהל.
4. ציין בסוף את שם קובץ הנוהל.
5. אם המידע באמת לא קיים בנהלים: "המידע אינו קיים בנהלים שצורפו".

מילון: פל"ת=פיקדון ללא תנועה | מו"ח=מורשה חתימה | ני"ע=ניירות ערך | מט"ח=מטבע חוץ | ס.פ./ס"פ=סוג פעולה | תמנון+=איסור הלבנת הון | תנופה=ניהול בקשות משכנתא | מאיה=מערכת סניפית | ריכוז תעריפוני=נוהל 25813
"""

# Self-Check uses Categorize: classifies the answer as PASS or RETRY
SELFCHECK_CATEGORIES = {
    "PASS": {
        "to": [MSG1_ID],
        "description": "התשובה ענתה על השאלה עם פרטים ספציפיים מנוהל (מספרים, מועדים, סעיפים, או טפסים).",
        "examples": [
            "התשובה כוללת מספרי סעיפים ושמות טפסים מהנוהל",
            "התשובה מפרטת תהליך עם שלבים ברורים",
            "התשובה כוללת סכומים ומועדים מדויקים"
        ]
    },
    "RETRY": {
        "to": [RETRIEVAL2_ID],
        "description": "התשובה גנרית, חסרה פרטים, או אומרת שהמידע אינו קיים. צריך לחפש שוב עם ניסוח חלופי.",
        "examples": [
            "המידע אינו קיים בנהלים שצורפו",
            "אין מידע על כך בנהלים",
            "תשובה כללית בלי מספרים או טפסים ספציפיים",
            "אני לא יכול לענות על השאלה"
        ]
    }
}

dsl = {
    "components": {
        "begin": {
            "downstream": [REWRITER_ID],
            "obj": {
                "component_name": "Begin",
                "params": {"prologue": "שלום! אני עוזר הבנק.", "inputs": {}}
            },
            "upstream": []
        },
        REWRITER_ID: {
            "downstream": [RETRIEVAL1_ID],
            "obj": {
                "component_name": "Agent",
                "params": {
                    "llm_id": LLM, "max_rounds": 1, "max_tokens": 256,
                    "maxTokensEnabled": True, "temperature": 0.0, "temperatureEnabled": True,
                    "sys_prompt": REWRITER_PROMPT,
                    "prompts": [{"role": "user", "content": "שאלה: {sys.query}\n\nפלט (שורה אחת):"}],
                    "outputs": {"content": {"type": "string", "value": ""}},
                    "tools": [], "cite": False, "max_retries": 2, "delay_after_error": 1,
                    "exception_method": None, "exception_default_value": "", "exception_goto": [],
                    "exception_comment": "", "frequencyPenaltyEnabled": False, "frequency_penalty": 0.0,
                    "presencePenaltyEnabled": False, "presence_penalty": 0.0,
                    "topPEnabled": False, "top_p": 1.0, "mcp": [],
                    "message_history_window_size": 0, "user_prompt": "", "visual_files_var": ""
                }
            },
            "upstream": ["begin"]
        },
        # First retrieval — uses sys.query (original)
        RETRIEVAL1_ID: {
            "downstream": [ANSWER1_ID],
            "obj": {
                "component_name": "Retrieval",
                "params": {
                    "kb_ids": [KB_HOZRIM], "dataset_ids": [KB_HOZRIM],
                    "rerank_id": RERANK, "top_n": 15, "top_k": 1024,
                    "similarity_threshold": 0.1, "keywords_similarity_weight": 0.7,
                    "use_kg": False, "cross_languages": [], "empty_response": "",
                    "memory_ids": [], "kb_vars": [], "meta_data_filter": {}, "toc_enhance": False,
                    "outputs": {"formalized_content": {"type": "string", "value": ""}},
                    "query": "{sys.query}"
                }
            },
            "upstream": [REWRITER_ID]
        },
        ANSWER1_ID: {
            "downstream": [SELFCHECK_ID],
            "obj": {
                "component_name": "Agent",
                "params": {
                    "llm_id": LLM, "max_rounds": 1, "max_tokens": 2048,
                    "maxTokensEnabled": True, "temperature": 0.1, "temperatureEnabled": True,
                    "sys_prompt": ANSWER_PROMPT,
                    "prompts": [{
                        "role": "user",
                        "content": "שאלה: {sys.query}\n\nנהלים רלוונטיים:\n{" + RETRIEVAL1_ID + "@formalized_content}\n\nתשובה (בעברית בלבד):"
                    }],
                    "outputs": {"content": {"type": "string", "value": ""}},
                    "tools": [], "cite": False, "max_retries": 2, "delay_after_error": 1,
                    "exception_method": None, "exception_default_value": "", "exception_goto": [],
                    "exception_comment": "", "frequencyPenaltyEnabled": False, "frequency_penalty": 0.0,
                    "presencePenaltyEnabled": False, "presence_penalty": 0.0,
                    "topPEnabled": False, "top_p": 1.0, "mcp": [],
                    "message_history_window_size": 0, "user_prompt": "", "visual_files_var": ""
                }
            },
            "upstream": [RETRIEVAL1_ID]
        },
        SELFCHECK_ID: {
            "downstream": [MSG1_ID, RETRIEVAL2_ID],
            "obj": {
                "component_name": "Categorize",
                "params": {
                    "llm_id": LLM, "max_tokens": 32, "maxTokensEnabled": True,
                    "temperature": 0.0, "temperatureEnabled": True,
                    "category_description": SELFCHECK_CATEGORIES,
                    "query": f"{{{ANSWER1_ID}@content}}",
                    "message_history_window_size": 1,
                    "max_retries": 2, "delay_after_error": 1,
                    "exception_method": None, "exception_default_value": "", "exception_goto": [],
                    "exception_comment": "",
                    "frequencyPenaltyEnabled": False, "frequency_penalty": 0.0,
                    "presencePenaltyEnabled": False, "presence_penalty": 0.0,
                    "topPEnabled": False, "top_p": 1.0,
                    "user_prompt": "", "visual_files_var": "",
                    "outputs": {"category_name": {"type": "string", "value": ""}}
                }
            },
            "upstream": [ANSWER1_ID]
        },
        # PASS path — direct to Reply
        MSG1_ID: {
            "downstream": [],
            "obj": {
                "component_name": "Message",
                "params": {"content": [f"{{{ANSWER1_ID}@content}}"]}
            },
            "upstream": [SELFCHECK_ID]
        },
        # RETRY path — re-retrieve with rewriter's output, then answer again
        RETRIEVAL2_ID: {
            "downstream": [ANSWER2_ID],
            "obj": {
                "component_name": "Retrieval",
                "params": {
                    "kb_ids": [KB_HOZRIM], "dataset_ids": [KB_HOZRIM],
                    "rerank_id": RERANK, "top_n": 15, "top_k": 1024,
                    "similarity_threshold": 0.0, "keywords_similarity_weight": 0.7,
                    "use_kg": False, "cross_languages": [], "empty_response": "",
                    "memory_ids": [], "kb_vars": [], "meta_data_filter": {}, "toc_enhance": False,
                    "outputs": {"formalized_content": {"type": "string", "value": ""}},
                    "query": f"{{{REWRITER_ID}@content}}"
                }
            },
            "upstream": [SELFCHECK_ID]
        },
        ANSWER2_ID: {
            "downstream": [MSG2_ID],
            "obj": {
                "component_name": "Agent",
                "params": {
                    "llm_id": LLM, "max_rounds": 1, "max_tokens": 2048,
                    "maxTokensEnabled": True, "temperature": 0.1, "temperatureEnabled": True,
                    "sys_prompt": ANSWER_PROMPT,
                    "prompts": [{
                        "role": "user",
                        "content": "שאלה: {sys.query}\n\nנהלים רלוונטיים:\n{" + RETRIEVAL2_ID + "@formalized_content}\n\nתשובה (בעברית בלבד):"
                    }],
                    "outputs": {"content": {"type": "string", "value": ""}},
                    "tools": [], "cite": False, "max_retries": 2, "delay_after_error": 1,
                    "exception_method": None, "exception_default_value": "", "exception_goto": [],
                    "exception_comment": "", "frequencyPenaltyEnabled": False, "frequency_penalty": 0.0,
                    "presencePenaltyEnabled": False, "presence_penalty": 0.0,
                    "topPEnabled": False, "top_p": 1.0, "mcp": [],
                    "message_history_window_size": 0, "user_prompt": "", "visual_files_var": ""
                }
            },
            "upstream": [RETRIEVAL2_ID]
        },
        MSG2_ID: {
            "downstream": [],
            "obj": {
                "component_name": "Message",
                "params": {"content": [f"{{{ANSWER2_ID}@content}}"]}
            },
            "upstream": [ANSWER2_ID]
        }
    },
    "globals": {"sys.history": [], "sys.query": "", "sys.user_id": "",
                "sys.conversation_turns": 0, "sys.files": [], "sys.date": ""},
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
            {"id": RETRIEVAL1_ID, "type": "retrievalNode", "position": {"x": 510, "y": 200},
             "measured": {"height": 80, "width": 200},
             "sourcePosition": "right", "targetPosition": "left",
             "data": {"label": "Retrieval", "name": "Retrieval_1",
                      "form": {"kb_ids": [KB_HOZRIM], "rerank_id": RERANK, "top_n": 15, "similarity_threshold": 0.1, "query": "{sys.query}"}}},
            {"id": ANSWER1_ID, "type": "agentNode", "position": {"x": 740, "y": 200},
             "measured": {"height": 80, "width": 200},
             "sourcePosition": "right", "targetPosition": "left",
             "data": {"label": "Agent", "name": "Answer_1",
                      "form": {"llm_id": LLM, "sys_prompt": ANSWER_PROMPT, "max_tokens": 2048, "temperature": 0.1, "tools": []}}},
            {"id": SELFCHECK_ID, "type": "categorizeNode", "position": {"x": 970, "y": 200},
             "measured": {"height": 80, "width": 200},
             "sourcePosition": "right", "targetPosition": "left",
             "data": {"label": "Categorize", "name": "Self_Check",
                      "form": {"llm_id": LLM, "category_description": SELFCHECK_CATEGORIES,
                               "query": f"{{{ANSWER1_ID}@content}}"}}},
            {"id": MSG1_ID, "type": "messageNode", "position": {"x": 1200, "y": 130},
             "measured": {"height": 50, "width": 200},
             "sourcePosition": "right", "targetPosition": "left",
             "data": {"label": "Message", "name": "Reply_PASS",
                      "form": {"content": [f"{{{ANSWER1_ID}@content}}"]}}},
            {"id": RETRIEVAL2_ID, "type": "retrievalNode", "position": {"x": 1200, "y": 270},
             "measured": {"height": 80, "width": 200},
             "sourcePosition": "right", "targetPosition": "left",
             "data": {"label": "Retrieval", "name": "Retrieval_2",
                      "form": {"kb_ids": [KB_HOZRIM], "rerank_id": RERANK, "top_n": 15, "similarity_threshold": 0.0,
                               "query": f"{{{REWRITER_ID}@content}}"}}},
            {"id": ANSWER2_ID, "type": "agentNode", "position": {"x": 1430, "y": 270},
             "measured": {"height": 80, "width": 200},
             "sourcePosition": "right", "targetPosition": "left",
             "data": {"label": "Agent", "name": "Answer_2",
                      "form": {"llm_id": LLM, "sys_prompt": ANSWER_PROMPT, "max_tokens": 2048, "temperature": 0.1, "tools": []}}},
            {"id": MSG2_ID, "type": "messageNode", "position": {"x": 1660, "y": 270},
             "measured": {"height": 50, "width": 200},
             "sourcePosition": "right", "targetPosition": "left",
             "data": {"label": "Message", "name": "Reply_RETRY",
                      "form": {"content": [f"{{{ANSWER2_ID}@content}}"]}}}
        ],
        "edges": [
            {"id": "e1", "source": "begin", "sourceHandle": "start", "target": REWRITER_ID, "targetHandle": "end"},
            {"id": "e2", "source": REWRITER_ID, "sourceHandle": "start", "target": RETRIEVAL1_ID, "targetHandle": "end"},
            {"id": "e3", "source": RETRIEVAL1_ID, "sourceHandle": "start", "target": ANSWER1_ID, "targetHandle": "end"},
            {"id": "e4", "source": ANSWER1_ID, "sourceHandle": "start", "target": SELFCHECK_ID, "targetHandle": "end"},
            {"id": "e5", "source": SELFCHECK_ID, "sourceHandle": "PASS", "target": MSG1_ID, "targetHandle": "end"},
            {"id": "e6", "source": SELFCHECK_ID, "sourceHandle": "RETRY", "target": RETRIEVAL2_ID, "targetHandle": "end"},
            {"id": "e7", "source": RETRIEVAL2_ID, "sourceHandle": "start", "target": ANSWER2_ID, "targetHandle": "end"},
            {"id": "e8", "source": ANSWER2_ID, "sourceHandle": "start", "target": MSG2_ID, "targetHandle": "end"}
        ]
    },
    "history": [], "messages": [], "path": [], "retrieval": [], "variables": []
}

new_id = get_uuid()
UserCanvas.insert({
    'id': new_id,
    'avatar': src.avatar,
    'user_id': TENANT,
    'title': 'banking_agentic_rag_v3',
    'description': 'Agentic RAG v3 — Full pattern with Self-Check loop. '
                   'Begin → Rewriter → Retrieval(sys.query) → Answer → Self-Check (PASS/RETRY) → '
                   'either Reply or → Retrieval(rewriter) → Answer_v2 → Reply.',
    'canvas_type': 'agent_canvas',
    'dsl': dsl,
    'permission': src.permission,
}).execute()

print(f"Created agent canvas:")
print(f"  id:    {new_id}")
print(f"  title: banking_agentic_rag_v3")
print()
print("Flow:")
print("  Begin → Query_Rewriter (gemma4)")
print("        → Retrieval_1 (uses sys.query)")
print("        → Answer_1 (gemma4, no tools)")
print("        → Self_Check (Categorize: PASS or RETRY)")
print("            ├─ PASS → Reply_PASS")
print("            └─ RETRY → Retrieval_2 (uses Rewriter output)")
print("                    → Answer_2 → Reply_RETRY")

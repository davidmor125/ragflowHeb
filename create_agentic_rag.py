"""Create an Agentic RAG canvas for the hozrim_poc KB.
Uses RAGFlow's Agent-with-tools pattern: a single Agent component with
Retrieval as a tool. The agent decides when to retrieve, can re-retrieve
with different queries, and produces a Hebrew banking-domain answer."""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas, Knowledgebase
from common.misc_utils import get_uuid
DB.connect(reuse_if_open=True)

KB_ID = '928f816a487a11f1a37a31aeaf1accf8'  # hozrim_poc
LLM   = 'gemma4:31b-cloud@Ollama'
RERANK = 'BAAI/bge-reranker-v2-m3@HuggingFace'

# Get an existing canvas to copy IDs and structure idioms from
src = UserCanvas.get(UserCanvas.id == 'e6fabcd6487211f1b5d9b35f7ee63b5f')
user_id = src.user_id

AGENT_ID = "Agent:" + get_uuid()[:14]
MSG_ID   = "Message:" + get_uuid()[:14]

SYS_PROMPT = """# תפקיד
אתה עוזר בנקאי מומחה. תפקידך לענות על שאלות בנקאיות על בסיס נהלים פנימיים שבמאגר.

# כללי עבודה
1. **תמיד השתמש בכלי Retrieval** למציאת המידע הרלוונטי לפני שאתה עונה.
2. אם התשובה הראשונית לא מספיק טובה — קרא ל-Retrieval **שוב** עם ניסוח אחר של השאלה.
3. ענה **רק על בסיס מה שאוחזר**. אסור להמציא.
4. ענה **בעברית** בלבד.

# כיצד לאחזר טוב יותר
- אם השאלה מכילה מונח כללי כמו "חשבון מקוון", הוסף הקשר ספציפי כשאתה מנסח את ה-query (לדוגמה: "תנאי הפקדה בחשבון מקוון יחיד").
- אם השאלה היא על עמלה ולא נמצא מידע — נסה לחפש "ריכוז תעריפוני" או "עלות שירות".
- אם השאלה מזכירה מערכת ספציפית (תמנון, תנופה, דולב, סניפומט) — כלול אותה בחיפוש.
- אם הצ'אנקים שאוחזרו לא ענו על השאלה — נסה ניסוח חלופי שלוש פעמים לכל היותר.

# פורמט תשובה
- ענה ישירות, בלי הקדמות.
- צטט מספרים, סכומים, גילאים, וריביות **בדיוק** כפי שמופיעים בנוהל.
- ציין בסוף את שם קובץ הנוהל.
- אם אחרי 3 ניסיונות אחזור לא מצאת תשובה ברורה: "המידע אינו קיים בנהלים שצורפו"."""

dsl = {
    "components": {
        "begin": {
            "downstream": [AGENT_ID],
            "obj": {
                "component_name": "Begin",
                "params": {
                    "prologue": "שלום! אני עוזר הבנק. שאל אותי על הנהלים והנחיות העבודה.",
                    "inputs": {}
                }
            },
            "upstream": []
        },
        AGENT_ID: {
            "downstream": [MSG_ID],
            "obj": {
                "component_name": "Agent",
                "params": {
                    "delay_after_error": 1,
                    "description": "Banking RAG agent",
                    "exception_comment": "",
                    "exception_default_value": "",
                    "exception_goto": [],
                    "exception_method": None,
                    "frequencyPenaltyEnabled": False,
                    "frequency_penalty": 0.7,
                    "llm_id": LLM,
                    "maxTokensEnabled": False,
                    "max_retries": 3,
                    "max_rounds": 5,        # allow up to 5 retrieval iterations
                    "max_tokens": 1024,
                    "mcp": [],
                    "message_history_window_size": 12,
                    "outputs": {"content": {"type": "string", "value": ""}},
                    "presencePenaltyEnabled": False,
                    "presence_penalty": 0.4,
                    "prompts": [{"content": "{sys.query}", "role": "user"}],
                    "sys_prompt": SYS_PROMPT,
                    "temperature": 0.1,
                    "temperatureEnabled": True,
                    "tools": [{
                        "component_name": "Retrieval",
                        "name": "Retrieval",
                        "params": {
                            "cross_languages": [],
                            "description": "Search the bank procedures knowledge base. Returns the most relevant chunks for a query. Use this for every banking question — call it again with a refined query if the first result wasn't sufficient.",
                            "empty_response": "המידע אינו קיים בנהלים שצורפו",
                            "kb_ids": [KB_ID],
                            "keywords_similarity_weight": 0.7,
                            "outputs": {"formalized_content": {"type": "string", "value": ""}},
                            "rerank_id": RERANK,
                            "similarity_threshold": 0.1,
                            "top_k": 1024,
                            "top_n": 15,
                            "use_kg": False
                        }
                    }],
                    "topPEnabled": False,
                    "top_p": 0.3,
                    "user_prompt": "",
                    "visual_files_var": ""
                }
            },
            "upstream": ["begin"]
        },
        MSG_ID: {
            "downstream": [],
            "obj": {
                "component_name": "Message",
                "params": {"content": [f"{{{AGENT_ID}@content}}"]}
            },
            "upstream": [AGENT_ID]
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
            {
                "data": {"label": "Begin", "name": "Begin"},
                "id": "begin",
                "measured": {"height": 50, "width": 200},
                "position": {"x": 50, "y": 200},
                "sourcePosition": "left",
                "targetPosition": "right",
                "type": "beginNode"
            },
            {
                "data": {
                    "form": {
                        "llm_id": LLM,
                        "max_rounds": 5,
                        "sys_prompt": SYS_PROMPT,
                        "temperature": 0.1,
                        "tools": [{
                            "component_name": "Retrieval",
                            "name": "Retrieval",
                            "params": {
                                "kb_ids": [KB_ID],
                                "rerank_id": RERANK,
                                "top_n": 15,
                                "top_k": 1024,
                                "similarity_threshold": 0.1,
                            }
                        }]
                    },
                    "label": "Agent",
                    "name": "BankingRAG_Agent"
                },
                "id": AGENT_ID,
                "measured": {"height": 80, "width": 200},
                "position": {"x": 350, "y": 200},
                "sourcePosition": "right",
                "targetPosition": "left",
                "type": "agentNode"
            },
            {
                "data": {
                    "form": {"content": [f"{{{AGENT_ID}@content}}"]},
                    "label": "Message",
                    "name": "Reply"
                },
                "id": MSG_ID,
                "measured": {"height": 50, "width": 200},
                "position": {"x": 650, "y": 200},
                "sourcePosition": "right",
                "targetPosition": "left",
                "type": "messageNode"
            }
        ],
        "edges": [
            {
                "id": f"xy-edge__beginstart-{AGENT_ID}end",
                "source": "begin",
                "sourceHandle": "start",
                "target": AGENT_ID,
                "targetHandle": "end"
            },
            {
                "id": f"xy-edge__{AGENT_ID}start-{MSG_ID}end",
                "source": AGENT_ID,
                "sourceHandle": "start",
                "target": MSG_ID,
                "targetHandle": "end"
            }
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
    'id':          new_id,
    'avatar':      src.avatar,
    'user_id':     user_id,
    'title':       'banking_agentic_rag',
    'description': 'Agentic RAG for hozrim_poc: single Agent with Retrieval tool. '
                   'Hebrew banking-domain prompt. Up to 5 retrieval rounds with self-refinement.',
    'canvas_type': 'agent_canvas',
    'dsl':         dsl,
    'permission':  src.permission,
}).execute()

print(f"Created agent canvas:")
print(f"  id:    {new_id}")
print(f"  title: banking_agentic_rag")
print(f"  KB:    hozrim_poc ({KB_ID})")
print(f"  LLM:   {LLM}")
print(f"  max_rounds: 5 (up to 5 retrieval iterations per question)")

# Save id for the eval runner
with open('/ragflow/_agent_id.json', 'w') as f:
    json.dump({'agent_id': new_id, 'kb_id': KB_ID}, f)

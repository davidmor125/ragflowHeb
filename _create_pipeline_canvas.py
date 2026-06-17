"""Build a clean pipeline canvas: Begin -> Retrieval -> Agent (no tools) -> Message.
- Uses gemma4:26b@Ollama (LOCAL, no Ollama Cloud quota).
- max_rounds=1 (no tool loop possible -> no thinking-leak).
- Strong system prompt: Hebrew only, no thinking, cite the procedure file.
- Retrieval: vec_weight=0.3, top_n=15, with multilingual reranker.
"""
import sys, json, uuid, datetime
sys.stdout.reconfigure(encoding="utf-8")
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)

NEW_ID = uuid.uuid1().hex
NEW_TITLE = "banking_pipeline_v1"

# A reference user_id from existing canvas
src = UserCanvas.get(UserCanvas.id == "54e45b8048a011f18e412992204f7aa3")
USER_ID = src.user_id
KB_ID = "dc0091ca46e211f196f633ac796a3d7a"
RERANK_ID = "BAAI/bge-reranker-v2-m3@HuggingFace"
LLM_ID = "gemma4:26b@Ollama"  # LOCAL — no quota

retrieval_node_name = "Retrieval:pipe1"
agent_node_name = "Agent:pipe1"
message_node_name = "Message:pipe1"

dsl = {
    "components": {
        "begin": {
            "downstream": [retrieval_node_name],
            "upstream": [],
            "obj": {
                "component_name": "Begin",
                "params": {
                    "prologue": "שלום! אני עוזר נהלי הבנק.",
                    "inputs": {},
                },
            },
        },
        retrieval_node_name: {
            "downstream": [agent_node_name],
            "upstream": ["begin"],
            "obj": {
                "component_name": "Retrieval",
                "params": {
                    "kb_ids": [KB_ID],
                    "dataset_ids": [KB_ID],
                    "rerank_id": RERANK_ID,
                    "top_n": 15,
                    "top_k": 1024,
                    "similarity_threshold": 0.1,
                    "keywords_similarity_weight": 0.3,
                    "vector_similarity_weight": 0.3,
                    "use_kg": False,
                    "cross_languages": [],
                    "empty_response": "",
                    "memory_ids": [],
                    "kb_vars": [],
                    "meta_data_filter": {},
                    "toc_enhance": False,
                    "query": "{sys.query}",
                    "outputs": {
                        "formalized_content": {"type": "string", "value": ""},
                    },
                },
            },
        },
        agent_node_name: {
            "downstream": [message_node_name],
            "upstream": [retrieval_node_name],
            "obj": {
                "component_name": "Agent",
                "params": {
                    "llm_id": LLM_ID,
                    "max_rounds": 1,
                    "max_tokens": 1500,
                    "maxTokensEnabled": True,
                    "temperature": 0.1,
                    "temperatureEnabled": True,
                    "sys_prompt": (
                        "אתה עוזר בנקאי שעונה רק על בסיס הנהלים שצורפו לשאלה.\n"
                        "\n"
                        "**חוקים מוחלטים — חובה לפעול לפיהם:**\n"
                        "1. ענה **בעברית בלבד**. אסור לכתוב באנגלית.\n"
                        "2. **אל תכתוב 'thinking', 'Step 1', 'Need to search', 'We need to'** — זה אסור.\n"
                        "3. אסור לקרוא לכלים, אסור לחפש שוב — קיבלת את כל המידע שיש לך.\n"
                        "4. ענה ישירות ובקצרה. אל תוסיף הקדמות.\n"
                        "5. צטט מספרי סעיפים, סכומים, מועדים, ושמות טפסים בדיוק כפי שמופיעים בנהלים.\n"
                        "6. **אם המידע באמת לא נמצא בנהלים שצורפו — כתוב בדיוק:** 'המידע אינו קיים בנהלים שצורפו'. אסור להמציא.\n"
                        "7. בסוף התשובה, ציין את שם קובץ הנוהל שממנו לקחת את המידע.\n"
                        "\n"
                        "מילון:\n"
                        "פל\"ת=פיקדון ללא תנועה | מו\"ח=מורשה חתימה | ני\"ע=ניירות ערך | מט\"ח=מטבע חוץ | "
                        "ס.פ./ס\"פ=סוג פעולה | תמנון+=איסור הלבנת הון | תנופה=ניהול בקשות משכנתא | "
                        "מאיה=מערכת סניפית | ריכוז תעריפוני=נוהל 25813\n"
                    ),
                    "prompts": [
                        {
                            "role": "user",
                            "content": (
                                "שאלה: {sys.query}\n"
                                "\n"
                                "נהלים רלוונטיים:\n"
                                "{" + retrieval_node_name + "@formalized_content}\n"
                                "\n"
                                "תשובה (עברית בלבד, ישירה, ללא thinking):"
                            ),
                        }
                    ],
                    "outputs": {"content": {"type": "string", "value": ""}},
                    "tools": [],
                    "cite": False,
                    "max_retries": 1,
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
                    "visual_files_var": "",
                },
            },
        },
        message_node_name: {
            "downstream": [],
            "upstream": [agent_node_name],
            "obj": {
                "component_name": "Message",
                "params": {
                    "content": ["{" + agent_node_name + "@content}"],
                },
            },
        },
    },
    "graph": {"nodes": [], "edges": []},
    "history": [],
    "messages": [],
    "path": [],
    "retrieval": [],
    "memory": [],
}

now = datetime.datetime.now()
UserCanvas.create(
    id=NEW_ID,
    user_id=USER_ID,
    title=NEW_TITLE,
    avatar=src.avatar,
    description="Pipeline RAG: Begin -> Retrieval -> LLM (no tools) -> Reply",
    canvas_type=src.canvas_type,
    dsl=dsl,
    permission=src.permission,
    create_time=int(now.timestamp() * 1000),
    create_date=now,
    update_time=int(now.timestamp() * 1000),
    update_date=now,
)

print(f"Created pipeline canvas")
print(f"  id={NEW_ID}")
print(f"  title={NEW_TITLE}")
print(f"  llm={LLM_ID}")
print(f"  vec_weight=0.3  top_n=15  reranker=bge-v2-m3")

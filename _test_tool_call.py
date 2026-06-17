"""Direct test of gemma4:31b-cloud's tool-calling capability via the same
LiteLLM path RAGFlow uses, with the same tool schema."""
import sys, json, asyncio, logging
sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO)

from common import settings as s
s.init_settings()
from api.db.db_models import DB
DB.connect(reuse_if_open=True)

# Build the same client RAGFlow's Agent uses
from api.db.services.llm_service import LLMBundle
from api.db.joint_services.tenant_model_service import get_model_config_by_type_and_name
from common.constants import LLMType

TENANT_ID = '2507563a42bd11f1a6bba9e87ac7a32c'
LLM = 'gemma4:31b-cloud@Ollama'
mc = get_model_config_by_type_and_name(TENANT_ID, LLMType.CHAT, LLM)
bundle = LLMBundle(TENANT_ID, mc)

# Define a tool with the exact schema RAGFlow generates
TOOL = [{
    "type": "function",
    "function": {
        "name": "search_my_dateset_0",
        "description": "Search bank procedures knowledge base. Returns relevant chunks for a Hebrew query.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query in Hebrew."
                }
            },
            "required": ["query"]
        }
    }
}]

class FakeSession:
    async def tool_call_async(self, name, args):
        print(f">>> TOOL CALLED: name={name}  args={args}")
        return "תוצאת חיפוש: נוהל 32328 — בקשה לעיון במידע."

bundle.bind_tools(FakeSession(), TOOL)

async def go():
    print(f"Model: {LLM}")
    print(f"Tool: search_my_dateset_0")
    print()

    # Simple system prompt explicitly telling it to call the tool
    sys_prompt = """אתה עוזר. כשמשתמש שואל שאלה — קרא לכלי search_my_dateset_0 עם השאלה כ-query."""
    history = [{"role": "user", "content": "כיצד לקוח יכול לבקש לעיין במידע?"}]

    print("--- Trying async_chat_with_tools (non-stream) ---")
    try:
        resp, tk = await bundle.async_chat_with_tools(sys_prompt, history, {"temperature": 0.0})
        print(f"Response: {repr(resp)[:500]}")
        print(f"Tokens: {tk}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

    print()
    print("--- Trying async_chat_streamly_with_tools ---")
    full = ""
    try:
        async for chunk in bundle.async_chat_streamly_with_tools(sys_prompt, history, {"temperature": 0.0}):
            if isinstance(chunk, str):
                full += chunk
                print(f"  chunk: {repr(chunk)[:80]}")
            else:
                print(f"  tokens: {chunk}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
    print()
    print(f"FULL: {full[:500]}")

asyncio.run(go())

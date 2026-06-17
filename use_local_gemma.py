"""Switch the agent to use local gemma4:26b (no cloud dependency).
The model is registered as image2text in TenantLLM, but it's a chat-capable
model — we add it as chat type and enable is_tools=True."""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas, TenantLLM, LLM
import datetime, time
def current_timestamp(): return int(time.time() * 1000)
DB.connect(reuse_if_open=True)

TENANT = '2507563a42bd11f1a6bba9e87ac7a32c'
AGENT_ID = '54e45b8048a011f18e412992204f7aa3'

# 1. Add gemma4:26b as a chat model (it's currently only image2text)
existing_chat = TenantLLM.get_or_none(
    (TenantLLM.tenant_id == TENANT) &
    (TenantLLM.llm_factory == 'Ollama') &
    (TenantLLM.llm_name == 'gemma4:26b') &
    (TenantLLM.model_type == 'chat')
)
if existing_chat:
    print("gemma4:26b is already registered as chat")
else:
    # Update the existing row to be type=chat
    TenantLLM.update(model_type='chat').where(
        (TenantLLM.tenant_id == TENANT) &
        (TenantLLM.llm_factory == 'Ollama') &
        (TenantLLM.llm_name == 'gemma4:26b')
    ).execute()
    print("Updated gemma4:26b model_type to chat")

# 2. Add LLM table entry with is_tools=True
existing_llm = LLM.get_or_none(
    (LLM.fid == 'Ollama') & (LLM.llm_name == 'gemma4:26b')
)
if existing_llm:
    LLM.update(is_tools=True).where(LLM.id == existing_llm.id).execute()
    print("Updated existing LLM row with is_tools=True")
else:
    LLM.create(
        fid='Ollama',
        llm_name='gemma4:26b',
        model_type='chat',
        max_tokens=8192,
        tags='LLM,CHAT',
        is_tools=True,
        status='1',
    )
    print("Created LLM row with is_tools=True")

# 3. Switch the Agent canvas to use it
NEW_LLM = 'gemma4:26b@Ollama'
canvas = UserCanvas.get(UserCanvas.id == AGENT_ID)
dsl = json.loads(json.dumps(canvas.dsl))

for cid, comp in dsl['components'].items():
    if comp['obj']['component_name'] == 'Agent':
        old = comp['obj']['params'].get('llm_id')
        comp['obj']['params']['llm_id'] = NEW_LLM
        print(f"Agent llm_id: {old} -> {NEW_LLM}")

for n in dsl.get('graph', {}).get('nodes', []):
    if n.get('data', {}).get('label') == 'Agent':
        n['data']['form']['llm_id'] = NEW_LLM

canvas.dsl = dsl
canvas.save()
print("Saved.")

# 4. Verify model_config returns is_tools=True
from api.db.joint_services.tenant_model_service import get_model_config_by_type_and_name
from common.constants import LLMType
mc = get_model_config_by_type_and_name(TENANT, LLMType.CHAT, NEW_LLM)
print(f"\nVerification: gemma4:26b is_tools = {mc.get('is_tools')}")

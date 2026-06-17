"""Register qwen3:14b in RAGFlow and switch the agent to use it."""
import sys, json, time, datetime
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas, TenantLLM, LLM
DB.connect(reuse_if_open=True)

TENANT = '2507563a42bd11f1a6bba9e87ac7a32c'
AGENT_ID = '54e45b8048a011f18e412992204f7aa3'
NAME = 'qwen3:14b'
NEW_LLM = f'{NAME}@Ollama'

# 1. Register in TenantLLM
existing = TenantLLM.get_or_none(
    (TenantLLM.tenant_id == TENANT) &
    (TenantLLM.llm_factory == 'Ollama') &
    (TenantLLM.llm_name == NAME)
)
if existing:
    if existing.model_type != 'chat':
        TenantLLM.update(model_type='chat').where(TenantLLM.id == existing.id).execute()
        print(f"Updated TenantLLM model_type to chat")
    else:
        print(f"TenantLLM already registered as chat")
else:
    # Use the same api_base as other Ollama models
    other = TenantLLM.get(
        (TenantLLM.tenant_id == TENANT) &
        (TenantLLM.llm_factory == 'Ollama')
    )
    now_ts = int(time.time() * 1000)
    now_dt = datetime.datetime.fromtimestamp(now_ts/1000).strftime('%Y-%m-%d %H:%M:%S')
    TenantLLM.create(
        create_time=now_ts, create_date=now_dt,
        update_time=now_ts, update_date=now_dt,
        tenant_id=TENANT,
        llm_factory='Ollama',
        model_type='chat',
        llm_name=NAME,
        api_key=other.api_key,
        api_base=other.api_base,
        max_tokens=8192,
        used_tokens=0,
        status='1',
    )
    print(f"Registered TenantLLM: {NAME} as chat")

# 2. Add LLM table entry with is_tools=True
existing_llm = LLM.get_or_none((LLM.fid == 'Ollama') & (LLM.llm_name == NAME))
if existing_llm:
    LLM.update(is_tools=True).where(LLM.id == existing_llm.id).execute()
    print(f"Updated LLM is_tools=True")
else:
    LLM.create(
        fid='Ollama',
        llm_name=NAME,
        model_type='chat',
        max_tokens=8192,
        tags='LLM,CHAT',
        is_tools=True,
        status='1',
    )
    print(f"Created LLM row with is_tools=True")

# 3. Switch the Agent canvas to use it
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

# 4. Verify
from api.db.joint_services.tenant_model_service import get_model_config_by_type_and_name
from common.constants import LLMType
mc = get_model_config_by_type_and_name(TENANT, LLMType.CHAT, NEW_LLM)
print(f"\nVerification:")
print(f"  llm_name: {mc.get('llm_name')}")
print(f"  factory:  {mc.get('llm_factory')}")
print(f"  is_tools: {mc.get('is_tools')}")
print(f"  api_base: {mc.get('api_base')}")

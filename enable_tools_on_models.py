"""Enable is_tools=True on the chat models we use, by inserting LLM
template rows with the matching llm_name. This is what RAGFlow checks
when it builds the model config for the Agent."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as s
s.init_settings()
from api.db.db_models import DB, LLM
DB.connect(reuse_if_open=True)

# Models we want to enable tool-calling for
MODELS = [
    {"llm_name": "gemma4:31b-cloud", "fid": "Ollama", "max_tokens": 8192},
    {"llm_name": "gpt-oss:120b-cloud", "fid": "Ollama", "max_tokens": 8192},
    {"llm_name": "gpt-oss:20b", "fid": "Ollama", "max_tokens": 8192},
]

for m in MODELS:
    existing = list(LLM.select().where(
        (LLM.fid == m["fid"]) & (LLM.llm_name == m["llm_name"])
    ))
    if existing:
        before = existing[0].is_tools
        LLM.update(is_tools=True).where(
            (LLM.fid == m["fid"]) & (LLM.llm_name == m["llm_name"])
        ).execute()
        print(f"  UPDATED  {m['llm_name']:30}  is_tools: {before} -> True")
    else:
        # Create a new template row
        LLM.create(
            fid=m["fid"],
            llm_name=m["llm_name"],
            model_type="chat",
            max_tokens=m["max_tokens"],
            tags="LLM,CHAT",
            is_tools=True,
            status="1",
        )
        print(f"  CREATED  {m['llm_name']:30}  with is_tools=True")

# Verify
print()
print("Verification:")
for m in MODELS:
    rows = list(LLM.select().where(
        (LLM.fid == m["fid"]) & (LLM.llm_name == m["llm_name"])
    ))
    if rows:
        print(f"  {m['llm_name']:30}  is_tools={rows[0].is_tools}")

# Now verify get_model_config returns is_tools=True
print()
print("get_model_config check:")
from api.db.joint_services.tenant_model_service import get_model_config_by_type_and_name
from common.constants import LLMType
TENANT = "2507563a42bd11f1a6bba9e87ac7a32c"
for m in MODELS:
    full = f"{m['llm_name']}@{m['fid']}"
    try:
        mc = get_model_config_by_type_and_name(TENANT, LLMType.CHAT, full)
        print(f"  {full:40}  is_tools={mc.get('is_tools')}")
    except Exception as e:
        print(f"  {full:40}  ERROR: {type(e).__name__}: {e}")

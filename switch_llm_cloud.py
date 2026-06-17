import sys
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as common_settings
common_settings.init_settings()
from api.db.db_models import DB, Tenant, TenantLLM

DB.connect(reuse_if_open=True)
TENANT_ID = "2507563a42bd11f1a6bba9e87ac7a32c"

existing = TenantLLM.select().where(
    (TenantLLM.tenant_id == TENANT_ID) &
    (TenantLLM.llm_factory == "Ollama") &
    (TenantLLM.llm_name == "gpt-oss:120b-cloud")
).first()

if not existing:
    src = TenantLLM.select().where(
        (TenantLLM.tenant_id == TENANT_ID) &
        (TenantLLM.llm_name == "gpt-oss:20b")
    ).first()
    TenantLLM.create(
        tenant_id=TENANT_ID,
        llm_factory="Ollama",
        model_type="chat",
        llm_name="gpt-oss:120b-cloud",
        api_base=src.api_base if src else "http://host.docker.internal:11434",
        api_key=src.api_key if src else "x",
        max_tokens=8192,
    )
    print("Created gpt-oss:120b-cloud as chat model")
else:
    print(f"Already exists: type={existing.model_type}")

Tenant.update(llm_id="gpt-oss:120b-cloud@Ollama").where(Tenant.id == TENANT_ID).execute()
t = Tenant.get(Tenant.id == TENANT_ID)
print(f"Tenant llm_id is now: {t.llm_id}")

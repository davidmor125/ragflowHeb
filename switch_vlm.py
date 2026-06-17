import sys
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as common_settings
common_settings.init_settings()

from api.db.db_models import DB, Tenant, TenantLLM, Document, Task

DB.connect(reuse_if_open=True)

# 1. Cancel running tasks for this doc
DOC_ID = "4166f44442cb11f19dd4bd85ecf60816"
print("=== STEP 1: Cancel current parse ===")
deleted_tasks = Task.delete().where(Task.doc_id == DOC_ID).execute()
print(f"Deleted {deleted_tasks} pending tasks")

from api.db.services.document_service import DocumentService
DocumentService.update_by_id(DOC_ID, {
    "progress": 1.0,
    "progress_msg": "[manually halted - switching to cloud VLM]",
    "run": "0",
})
print("Doc state set to halted")

# 2. Register gemma4:31b-cloud as image2text in tenant
print()
print("=== STEP 2: Register gemma4:31b-cloud ===")
tenant = Tenant.select().where(Tenant.id != "b721c9de9f5e44a988b27c0a6dd0b15c").first()
print(f"Tenant: {tenant.id[:12]}...")

# Add a new TenantLLM row for gemma4:31b-cloud
existing = TenantLLM.select().where(
    (TenantLLM.tenant_id == tenant.id) &
    (TenantLLM.llm_factory == "Ollama") &
    (TenantLLM.llm_name == "gemma4:31b-cloud")
).first()

if existing:
    print(f"Already exists: {existing.llm_name} type={existing.model_type}")
    if existing.model_type != "image2text":
        TenantLLM.update(model_type="image2text").where(
            (TenantLLM.tenant_id == tenant.id) &
            (TenantLLM.llm_factory == "Ollama") &
            (TenantLLM.llm_name == "gemma4:31b-cloud")
        ).execute()
        print("Updated type to image2text")
else:
    # Copy settings from existing gemma4:26b row
    src = TenantLLM.select().where(
        (TenantLLM.tenant_id == tenant.id) &
        (TenantLLM.llm_name == "gemma4:26b")
    ).first()
    TenantLLM.create(
        tenant_id=tenant.id,
        llm_factory="Ollama",
        model_type="image2text",
        llm_name="gemma4:31b-cloud",
        api_base=src.api_base if src else "http://host.docker.internal:11434",
        api_key=src.api_key if src else "x",
        max_tokens=8192,
    )
    print(f"Created TenantLLM row for gemma4:31b-cloud")

# 3. Set tenant's default img2txt_id
print()
print("=== STEP 3: Set as default VLM ===")
Tenant.update(img2txt_id="gemma4:31b-cloud@Ollama").where(Tenant.id == tenant.id).execute()
t = Tenant.get(Tenant.id == tenant.id)
print(f"Tenant img2txt_id is now: {t.img2txt_id}")
print()
print("ALL DONE.")

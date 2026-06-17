"""Find the API base URL configured for gemma4:26b in TenantLLM and probe it."""
import sys, json
sys.stdout.reconfigure(encoding="utf-8")
from common import settings as s
s.init_settings()
from api.db.db_models import DB, TenantLLM
DB.connect(reuse_if_open=True)

TENANT = "2507563a42bd11f1a6bba9e87ac7a32c"

for r in TenantLLM.select().where((TenantLLM.tenant_id == TENANT) & (TenantLLM.model_type == "chat")):
    print(f"name={r.llm_name:30} factory={r.llm_factory:15} api_base={r.api_base!r}  api_key={'***' if r.api_key else '(none)'}")

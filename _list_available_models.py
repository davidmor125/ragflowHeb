"""List all chat models configured in this tenant, grouped by likely-availability."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from common import settings as s
s.init_settings()
from api.db.db_models import DB, TenantLLM, LLM
DB.connect(reuse_if_open=True)

TENANT = "2507563a42bd11f1a6bba9e87ac7a32c"

rows = list(TenantLLM.select().where(TenantLLM.tenant_id == TENANT))
print(f"Tenant has {len(rows)} configured model rows")
print()

# Bucket: cloud-rate-limited vs not
print("=" * 70)
print(f"{'model':45} {'factory':20} {'is_tools':8}")
print("=" * 70)
for r in rows:
    if r.model_type != 'chat': continue
    llm_row = list(LLM.select().where((LLM.llm_name == r.llm_name) & (LLM.fid == r.llm_factory)))
    is_tools = llm_row[0].is_tools if llm_row else "N/A"
    note = ""
    if "cloud" in r.llm_name.lower():
        note = "  ← OLLAMA CLOUD (rate-limited)"
    elif r.llm_factory == "Ollama":
        note = "  ← Ollama LOCAL"
    elif r.llm_factory in ("OpenAI", "Anthropic", "Gemini", "DeepSeek", "Together AI"):
        note = f"  ← {r.llm_factory} (external)"
    print(f"{r.llm_name:45} {r.llm_factory:20} {str(is_tools):8}{note}")

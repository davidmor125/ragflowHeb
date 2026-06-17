import sys
sys.stdout.reconfigure(encoding='utf-8')
from api.db.db_models import DB, Tenant, TenantLLM
DB.connect(reuse_if_open=True)
print('=== Tenant default models ===')
for t in Tenant.select():
    print(f'tenant={t.id[:8]}... llm_id={t.llm_id} embd_id={t.embd_id} img2txt_id={t.img2txt_id} rerank_id={t.rerank_id}')
print()
print('=== Configured TenantLLMs ===')
for r in TenantLLM.select():
    print(f'  {r.llm_factory}/{r.llm_name} type={r.model_type}')

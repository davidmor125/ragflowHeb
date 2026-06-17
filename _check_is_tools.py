import sys
sys.stdout.reconfigure(encoding="utf-8")
from common import settings as s
s.init_settings()
from api.db.db_models import DB, LLM
DB.connect(reuse_if_open=True)

for name in ["gemma4:31b-cloud", "gpt-oss:120b-cloud", "gpt-oss:20b", "qwen3:14b", "gemma4:26b"]:
    rows = list(LLM.select().where(LLM.llm_name == name))
    if not rows:
        print(f"{name}: NO ROW IN LLM TABLE")
        continue
    for r in rows:
        print(f"{name} (factory={r.fid}): is_tools={r.is_tools}  max_tokens={r.max_tokens}  model_type={r.model_type}")

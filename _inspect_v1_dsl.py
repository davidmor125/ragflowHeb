import sys, json
sys.stdout.reconfigure(encoding="utf-8")
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)

AGENT_ID = "54e45b8048a011f18e412992204f7aa3"  # v1
c = UserCanvas.get(UserCanvas.id == AGENT_ID)
dsl = c.dsl
print("title:", c.title)
print("components keys:", list(dsl.get("components", {}).keys()))
print()
for name, comp in dsl.get("components", {}).items():
    obj = comp.get("obj", {})
    ctype = obj.get("component_name", "?")
    params = obj.get("params", {}) or {}
    llm_id = params.get("llm_id") or params.get("llm_setting_id") or params.get("model")
    print(f"  {name}  type={ctype}  llm_id={llm_id}  max_rounds={params.get('max_rounds')}  cite={params.get('cite')}")

"""Clone v1 canvas, swap LLM to gemma4:26b (LOCAL), save as new canvas."""
import sys, json, uuid, copy, datetime
sys.stdout.reconfigure(encoding="utf-8")
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)

SRC_ID = "54e45b8048a011f18e412992204f7aa3"  # v1
NEW_ID = uuid.uuid1().hex
NEW_TITLE = "banking_agentic_rag_gemma26_local"

src = UserCanvas.get(UserCanvas.id == SRC_ID)
new_dsl = copy.deepcopy(src.dsl)

swapped = []
for name, comp in new_dsl.get("components", {}).items():
    obj = comp.get("obj", {})
    if obj.get("component_name") == "Agent":
        params = obj.setdefault("params", {})
        old = params.get("llm_id")
        params["llm_id"] = "gemma4:26b@Ollama"
        swapped.append((name, old, params["llm_id"]))

now = datetime.datetime.now()
UserCanvas.create(
    id=NEW_ID,
    user_id=src.user_id,
    title=NEW_TITLE,
    avatar=src.avatar,
    description=(src.description or "") + " [gemma4:26b LOCAL]",
    canvas_type=src.canvas_type,
    dsl=new_dsl,
    permission=src.permission,
    create_time=int(now.timestamp() * 1000),
    create_date=now,
    update_time=int(now.timestamp() * 1000),
    update_date=now,
)

print(f"Created canvas id={NEW_ID}  title={NEW_TITLE}")
for name, old, new in swapped:
    print(f"  swapped {name}: {old} -> {new}")

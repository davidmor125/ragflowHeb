"""Show full DSL of v3 canvas (which has Retrieval node, not tool) — copy that pattern."""
import sys, json
sys.stdout.reconfigure(encoding="utf-8")
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)

V3_ID = "05aea11c495211f180b9273574f6967d"
c = UserCanvas.get(UserCanvas.id == V3_ID)
print("title:", c.title)
print()
print(json.dumps(c.dsl, ensure_ascii=False, indent=2))

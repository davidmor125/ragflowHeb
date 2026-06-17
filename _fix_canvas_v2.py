"""Fix the canvas v2 DSL: keywords_similarity_weight 0.3 -> 0.7 (so vector_weight=0.3, good for Hebrew)."""
import sys, json
sys.stdout.reconfigure(encoding="utf-8")
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)

V2_ID = "22c30f2049db11f18c556f95756a453d"
c = UserCanvas.get(UserCanvas.id == V2_ID)
dsl = dict(c.dsl)

retrieval_node = dsl["components"]["Retrieval:pipe1"]
params = retrieval_node["obj"]["params"]
print(f"BEFORE: keywords_similarity_weight={params.get('keywords_similarity_weight')}  vector_similarity_weight={params.get('vector_similarity_weight')}")

# The retriever interprets keywords_similarity_weight by computing (1 - keywords_similarity_weight) and passing
# it as vector_similarity_weight. To get vector_weight=0.3 we need keywords_similarity_weight=0.7.
params["keywords_similarity_weight"] = 0.7
# vector_similarity_weight is unused by the canvas code path (it computes from keywords_similarity_weight).
# But set it for consistency.
params["vector_similarity_weight"] = 0.3

print(f"AFTER:  keywords_similarity_weight={params.get('keywords_similarity_weight')}  vector_similarity_weight={params.get('vector_similarity_weight')}")

# Save back
import datetime
now = datetime.datetime.now()
c.dsl = dsl
c.update_time = int(now.timestamp() * 1000)
c.update_date = now
c.save()

print(f"\nv2 canvas {V2_ID} updated")

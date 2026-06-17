import sys, datetime
sys.stdout.reconfigure(encoding="utf-8")
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)
V1_ID = "708c8bca49cf11f1bcd66b39e390ca8c"
c = UserCanvas.get(UserCanvas.id == V1_ID)
dsl = dict(c.dsl)
params = dsl["components"]["Retrieval:pipe1"]["obj"]["params"]
print("v1 BEFORE: kw_w=" + str(params.get("keywords_similarity_weight")))
params["keywords_similarity_weight"] = 0.7
params["vector_similarity_weight"] = 0.3
print("v1 AFTER:  kw_w=" + str(params.get("keywords_similarity_weight")))
now = datetime.datetime.now()
c.dsl = dsl
c.update_time = int(now.timestamp() * 1000)
c.update_date = now
c.save()
print("v1 updated")

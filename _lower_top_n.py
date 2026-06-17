"""Lower top_n from 15 to 5 in canvas v2 to fit gpt-oss:20b."""
import sys, datetime
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)

CANVAS_ID = '22c30f2049db11f18c556f95756a453d'
c = UserCanvas.get(UserCanvas.id == CANVAS_ID)
dsl = dict(c.dsl)
ret = dsl['components']['Retrieval:pipe1']['obj']['params']
print(f"BEFORE: top_n={ret.get('top_n')}")
ret['top_n'] = 5
print(f"AFTER:  top_n=5")

now = datetime.datetime.now()
c.dsl = dsl
c.update_time = int(now.timestamp() * 1000)
c.update_date = now
c.save()
print("saved")

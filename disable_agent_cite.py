"""Turn OFF the cite flag on the agent so it doesn't try to do
the English citation_plus pass (which is hard-coded to English)."""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)

AGENT_ID = '54e45b8048a011f18e412992204f7aa3'
canvas = UserCanvas.get(UserCanvas.id == AGENT_ID)
dsl = json.loads(json.dumps(canvas.dsl))

for cid, comp in dsl['components'].items():
    if comp['obj']['component_name'] == 'Agent':
        before = comp['obj']['params'].get('cite')
        comp['obj']['params']['cite'] = False
        print(f"  components.{cid}.cite: {before} -> False")

for n in dsl.get('graph', {}).get('nodes', []):
    if n.get('data', {}).get('label') == 'Agent':
        before = n['data']['form'].get('cite')
        n['data']['form']['cite'] = False
        print(f"  graph node cite: {before} -> False")

canvas.dsl = dsl
canvas.save()
print("Saved.")

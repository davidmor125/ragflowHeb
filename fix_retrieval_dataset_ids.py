"""Set dataset_ids on the Retrieval tool (the new param name)."""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)

AGENT_ID = '54e45b8048a011f18e412992204f7aa3'
KB_ID = '928f816a487a11f1a37a31aeaf1accf8'

c = UserCanvas.get(UserCanvas.id == AGENT_ID)
dsl = json.loads(json.dumps(c.dsl))

for cid, comp in dsl['components'].items():
    if comp['obj']['component_name'] == 'Agent':
        for tool in comp['obj']['params'].get('tools', []):
            if tool.get('component_name') == 'Retrieval':
                tool['params']['dataset_ids'] = [KB_ID]
                tool['params']['kb_ids'] = [KB_ID]   # keep for backward compat
                print(f"Set dataset_ids = [{KB_ID}]")

for n in dsl.get('graph', {}).get('nodes', []):
    if n.get('data', {}).get('label') == 'Agent':
        for tool in n['data']['form'].get('tools', []):
            if tool.get('component_name') == 'Retrieval':
                tool['params']['dataset_ids'] = [KB_ID]
                tool['params']['kb_ids'] = [KB_ID]

c.dsl = dsl
c.save()
print("Saved.")

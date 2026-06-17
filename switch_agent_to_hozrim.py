"""Point the agent at the full hozrim KB (646 docs) instead of hozrim_poc."""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)

AGENT_ID = '54e45b8048a011f18e412992204f7aa3'
HOZRIM   = 'dc0091ca46e211f196f633ac796a3d7a'  # full 646-doc KB

c = UserCanvas.get(UserCanvas.id == AGENT_ID)
dsl = json.loads(json.dumps(c.dsl))

for cid, comp in dsl['components'].items():
    if comp['obj']['component_name'] == 'Agent':
        for tool in comp['obj']['params'].get('tools', []):
            if tool.get('component_name') == 'Retrieval':
                old_kb = tool['params'].get('kb_ids')
                tool['params']['kb_ids']      = [HOZRIM]
                tool['params']['dataset_ids'] = [HOZRIM]
                print(f"Retrieval kb_ids: {old_kb} -> [{HOZRIM}] (hozrim, 646 docs)")

for n in dsl.get('graph', {}).get('nodes', []):
    if n.get('data', {}).get('label') == 'Agent':
        for tool in n['data']['form'].get('tools', []):
            if tool.get('component_name') == 'Retrieval':
                tool['params']['kb_ids']      = [HOZRIM]
                tool['params']['dataset_ids'] = [HOZRIM]

c.dsl = dsl
c.save()
print("Saved. Agent now searches the full hozrim KB.")

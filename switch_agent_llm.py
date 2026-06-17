"""Switch the agent's LLM to gpt-oss:120b-cloud (better tool-calling)."""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)

AGENT_ID = '54e45b8048a011f18e412992204f7aa3'
NEW_LLM = 'gpt-oss:120b-cloud@Ollama'

canvas = UserCanvas.get(UserCanvas.id == AGENT_ID)
dsl = json.loads(json.dumps(canvas.dsl))

for cid, comp in dsl['components'].items():
    if comp['obj']['component_name'] == 'Agent':
        old = comp['obj']['params'].get('llm_id')
        comp['obj']['params']['llm_id'] = NEW_LLM
        print(f"components.{cid}.llm_id: {old} -> {NEW_LLM}")

for n in dsl.get('graph', {}).get('nodes', []):
    if n.get('data', {}).get('label') == 'Agent':
        n['data']['form']['llm_id'] = NEW_LLM
        print(f"graph node updated: llm_id -> {NEW_LLM}")

canvas.dsl = dsl
canvas.save()
print("Saved.")

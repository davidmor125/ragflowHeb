"""Call the Retrieval tool directly from the agent canvas to see what it returns."""
import sys, json, asyncio, logging, os
os.environ['COMPONENT_EXEC_TIMEOUT'] = '180'
sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(name)s: %(message)s')

from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)
from agent.canvas import Canvas

AGENT_ID = '54e45b8048a011f18e412992204f7aa3'
canvas_obj = UserCanvas.get(UserCanvas.id == AGENT_ID)

async def go():
    cnvs = Canvas(json.dumps(canvas_obj.dsl), tenant_id=canvas_obj.user_id, canvas_id=canvas_obj.id)
    # Find the Agent component
    agent_id = None
    for cid, comp in cnvs.components.items():
        if comp['obj'].component_name == 'Agent':
            agent_id = cid
            break
    print(f'Agent component id: {agent_id}')

    agent_obj = cnvs.components[agent_id]['obj']
    print(f'Agent has {len(agent_obj.tools)} tools')
    for tname, tool in agent_obj.tools.items():
        print(f'  tool: {tname}  type={type(tool).__name__}')

    # Try to invoke the retrieval tool directly through the toolcall_session
    print('\n--- Calling retrieval tool directly ---')
    result = await agent_obj.toolcall_session.tool_call_async(
        'search_my_dateset_0',
        {'query': 'עיון במידע השמור במאגרי הבנק'}
    )
    print(f'\nResult type: {type(result).__name__}')
    print(f'Result length: {len(str(result))} chars')
    print(f'First 500: {str(result)[:500]}')
    print(f'Last 200: {str(result)[-200:]}')

asyncio.run(go())

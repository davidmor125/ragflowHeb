"""Smoke test the agent runner on a single question."""
import sys, os, json, asyncio, logging
# CRITICAL: bump tool exec timeout (default is 12s, Hebrew RAG calls take 10-22s)
os.environ['COMPONENT_EXEC_TIMEOUT'] = '180'
sys.stdout.reconfigure(encoding='utf-8')

# Enable verbose logging from RAGFlow internals
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(name)s: %(message)s')
logging.getLogger('elastic_transport.transport').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('LiteLLM').setLevel(logging.INFO)

from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)
from agent.canvas import Canvas

AGENT_ID = '54e45b8048a011f18e412992204f7aa3'
canvas = UserCanvas.get(UserCanvas.id == AGENT_ID)

async def go():
    print(f"Running agent: {canvas.title}")
    cnvs = Canvas(json.dumps(canvas.dsl), tenant_id=canvas.user_id, canvas_id=canvas.id)
    print(f"Canvas instantiated. components: {len(cnvs.components)}")
    print()

    Q = "כיצד יכול לקוח לבקש לעיין במידע השמור במאגרי הבנק אודות חשבונו?"
    print(f"Question: {Q}")
    print()

    answer_parts = []
    chunks = []
    n = 0
    async for ev in cnvs.run(query=Q):
        n += 1
        if not isinstance(ev, dict): continue
        et = ev.get('event','')
        data = ev.get('data') or {}
        # Print every event verbosely
        data_str = json.dumps(data, ensure_ascii=False)[:300] if isinstance(data, dict) else str(data)[:300]
        print(f'  ev #{n}  event={et}  data: {data_str}')
        if et == 'message':
            c = data.get('content') if isinstance(data, dict) else None
            if c: answer_parts.append(c)
        elif et == 'message_end':
            c = data.get('content') if isinstance(data, dict) else None
            if c:
                answer_parts = [c]
        elif et in ('node_finished','workflow_finished'):
            outputs = data.get('outputs') or {}
            for k, v in outputs.items() if isinstance(outputs, dict) else []:
                if isinstance(v, dict) and v.get('chunks'):
                    chunks = v['chunks']

    full = ''.join(answer_parts)
    print(f'\nTotal events: {n}')
    print(f'Total chunks captured: {len(chunks)}')
    print()
    print('=== ANSWER ===')
    print(full)

asyncio.run(go())

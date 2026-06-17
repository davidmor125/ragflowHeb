"""Single-question smoke test on gemma4:26b local."""
import sys, json, asyncio, time, re
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)
from agent.canvas import Canvas

AGENT_ID = '0df2bc30499011f1ae9a9585deaa4ea2'  # gemma26 local

QUESTION = 'איך עושים העברת מט"ח לאיחוד האמירויות'

async def ask(question):
    fresh = UserCanvas.get(UserCanvas.id == AGENT_ID)
    cnvs = Canvas(json.dumps(fresh.dsl), tenant_id=fresh.user_id, canvas_id=fresh.id)
    answer_parts = []
    final = None
    n_events = 0
    try:
        async for ev in cnvs.run(query=question):
            n_events += 1
            if not isinstance(ev, dict): continue
            data = ev.get('data') or {}
            et = ev.get('event','')
            if et == 'message':
                c = data.get('content') if isinstance(data, dict) else None
                if c: answer_parts.append(c)
            elif et == 'message_end':
                c = data.get('content') if isinstance(data, dict) else None
                if c: final = c
            elif et == 'node_finished' and isinstance(data, dict):
                cname = data.get('component_name','')
                outputs = data.get('outputs') or {}
                if (cname == 'Reply' or data.get('component_type') == 'Message') and isinstance(outputs, dict):
                    if outputs.get('content'):
                        final = outputs['content']
    except Exception as e:
        return f"[ERROR: {type(e).__name__}: {str(e)[:300]}]", n_events
    return final if final else "".join(answer_parts), n_events

async def main():
    t0 = time.time()
    print(f"asking: {QUESTION}")
    print()
    ans, n_events = await ask(QUESTION)
    print(f"events received: {n_events}")
    print(f"elapsed: {time.time()-t0:.0f}s")
    print(f"len: {len(ans)}")
    print(f"first 800 chars: {ans[:800]}")
    print()
    print(f"last 800 chars: {ans[-800:]}")

asyncio.run(main())

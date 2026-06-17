"""Smoke test the v2 Agentic RAG."""
import sys, json, asyncio, time
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)
from agent.canvas import Canvas

AGENT_ID = '08690e36494f11f1abe3f75f35493e6a'  # banking_agentic_rag_v2
canvas = UserCanvas.get(UserCanvas.id == AGENT_ID)

QUESTION = "כיצד יכול לקוח לבקש לעיין במידע השמור במאגרי הבנק אודות חשבונו?"

async def go():
    cnvs = Canvas(json.dumps(canvas.dsl), tenant_id=canvas.user_id, canvas_id=canvas.id)
    answer_parts = []
    final = None
    print("Events:")
    t0 = time.time()
    n = 0
    async for ev in cnvs.run(query=QUESTION):
        n += 1
        if not isinstance(ev, dict): continue
        et = ev.get('event','')
        data = ev.get('data') or {}
        if et == 'node_started':
            cname = data.get('component_name','?') if isinstance(data, dict) else '?'
            ctype = data.get('component_type','?') if isinstance(data, dict) else '?'
            print(f"  [{time.time()-t0:5.1f}s] node started: {cname} ({ctype})")
        elif et == 'node_finished':
            cname = data.get('component_name','?') if isinstance(data, dict) else '?'
            outputs = data.get('outputs') or {}
            output_preview = ''
            if isinstance(outputs, dict):
                if 'content' in outputs:
                    output_preview = str(outputs['content'])[:100]
                elif 'formalized_content' in outputs:
                    output_preview = f"<{len(str(outputs['formalized_content']))} chars of context>"
            print(f"  [{time.time()-t0:5.1f}s] node done:    {cname}  output: {output_preview}")
        elif et == 'message':
            c = data.get('content') if isinstance(data, dict) else None
            if c: answer_parts.append(c)
        elif et == 'message_end':
            c = data.get('content') if isinstance(data, dict) else None
            if c: final = c
    elapsed = time.time() - t0
    answer = final if final else "".join(answer_parts)
    print()
    print(f"Total: {n} events, {elapsed:.1f}s")
    print(f"Answer length: {len(answer)} chars")
    print()
    print('=== ANSWER ===')
    print(answer)

asyncio.run(go())

"""Smoke test the pipeline canvas on one of the thinking-only failures.
Goal: verify it produces a real Hebrew answer instead of English thinking-loop.
"""
import sys, json, asyncio, time, re
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)
from agent.canvas import Canvas

CANVAS_ID = '708c8bca49cf11f1bcd66b39e390ca8c'

QUESTION = 'מתי צריך להקים בקשות אשראי במערכת בקשות אשראי ללקוח פרטי?'

async def ask(question):
    fresh = UserCanvas.get(UserCanvas.id == CANVAS_ID)
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
    elapsed = time.time() - t0
    print(f"events: {n_events}  elapsed: {elapsed:.0f}s  len: {len(ans)}")
    print()
    print(f"FULL ANSWER:")
    print(ans)
    print()
    # Quick analysis
    eng = sum(1 for c in ans if 'a'<=c.lower()<='z')
    heb = sum(1 for c in ans if '֐'<=c<='׿')
    print(f"Hebrew chars: {heb}  English chars: {eng}  ratio: {heb/(heb+eng+1):.2f}")

asyncio.run(main())

"""Run canvas v2 on n=33 with the patched llm.py — observe what LLM gets."""
import sys, json, asyncio
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)
from agent.canvas import Canvas

CANVAS_ID = '22c30f2049db11f18c556f95756a453d'  # pipeline v2
QUESTION = 'באיזה מקרים משתמשים בפעולת דיווח ערבות ללא טופל ממוכן?'

async def main():
    fresh = UserCanvas.get(UserCanvas.id == CANVAS_ID)
    cnvs = Canvas(json.dumps(fresh.dsl), tenant_id=fresh.user_id, canvas_id=fresh.id)
    print(f"Q: {QUESTION}", flush=True)
    print('--- canvas events ---', flush=True)
    n = 0
    final = None
    async for ev in cnvs.run(query=QUESTION):
        n += 1
        if not isinstance(ev, dict): continue
        et = ev.get('event','')
        data = ev.get('data', {}) or {}
        if et == 'node_finished':
            cname = data.get('component_name', '?')
            outputs = data.get('outputs', {}) or {}
            print(f"[CANVAS] node_finished: {cname}", flush=True)
            for k, v in (outputs or {}).items():
                vstr = str(v)
                vstr_show = vstr[:150] + (f' ...[{len(vstr)} total]' if len(vstr) > 150 else '')
                print(f"[CANVAS]   {k} = {vstr_show}", flush=True)
        elif et == 'message_end':
            c = data.get('content') if isinstance(data, dict) else None
            if c:
                final = c
        if n > 200:
            break
    print('--- final answer ---', flush=True)
    print(f"len: {len(final or '')}", flush=True)
    print((final or '')[-1500:], flush=True)

asyncio.run(main())

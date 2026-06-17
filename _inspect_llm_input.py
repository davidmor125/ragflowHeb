"""Trace what the LLM in the pipeline actually receives.
We'll instrument by hand: run the canvas, capture node inputs/outputs.
"""
import sys, json, asyncio
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)
from agent.canvas import Canvas

CANVAS_ID = '708c8bca49cf11f1bcd66b39e390ca8c'
QUESTION = 'באיזה מקרים משתמשים בפעולת דיווח ערבות ללא טופל ממוכן?'  # n=33

async def main():
    fresh = UserCanvas.get(UserCanvas.id == CANVAS_ID)
    cnvs = Canvas(json.dumps(fresh.dsl), tenant_id=fresh.user_id, canvas_id=fresh.id)
    print(f"Q: {QUESTION}\n")
    n = 0
    async for ev in cnvs.run(query=QUESTION):
        n += 1
        if not isinstance(ev, dict): continue
        et = ev.get('event','')
        data = ev.get('data', {}) or {}
        if et == 'node_finished':
            cname = data.get('component_name', '?')
            outputs = data.get('outputs', {}) or {}
            print(f"--- node_finished: {cname}")
            for k, v in (outputs or {}).items():
                vstr = str(v)[:500]
                print(f"  {k} = {vstr}")
            print()
        elif et == 'node_started':
            cname = data.get('component_name', '?')
            inputs = data.get('inputs', {}) or {}
            print(f">>> node_started: {cname}")
            for k, v in inputs.items():
                vstr = str(v)[:500]
                print(f"  IN {k} = {vstr}")
            print()
        if n > 50:
            break
    print(f"\ntotal events: {n}")

asyncio.run(main())

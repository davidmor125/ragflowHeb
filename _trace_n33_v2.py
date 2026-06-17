"""Trace v2 canvas on n=33 — capture EVERY node's input/output to see if LLM got chunks."""
import os
os.environ["COMPONENT_EXEC_TIMEOUT"] = "120"
os.environ["ENABLE_TIMEOUT_ASSERTION"] = ""  # explicitly off

import sys, json, asyncio
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)
from agent.canvas import Canvas

CANVAS_ID = '22c30f2049db11f18c556f95756a453d'  # v2
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
                vstr = str(v)
                if len(vstr) > 800:
                    vstr = vstr[:400] + f' ...[{len(str(v))} total]... ' + vstr[-300:]
                print(f"  {k} = {vstr}")
            print()
        if n > 50:
            break

asyncio.run(main())

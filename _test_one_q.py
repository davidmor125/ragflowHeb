"""Test one question through the agent with current config (gpt-oss:120b),
print the FULL answer to see where it cuts off."""
import sys, json, asyncio, time, re
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)
from agent.canvas import Canvas

AGENT_ID = '54e45b8048a011f18e412992204f7aa3'
canvas_obj = UserCanvas.get(UserCanvas.id == AGENT_ID)

QUESTION = "האם בדוח חריגים מול הצהרות לקוח כלולות הפקדות מזומן מעל 5,000 ₪"
print(f"Q: {QUESTION}")
print()

async def go():
    cnvs = Canvas(json.dumps(canvas_obj.dsl), tenant_id=canvas_obj.user_id, canvas_id=canvas_obj.id)
    answer_parts = []
    final_message_content = None
    tool_call_count = 0
    t0 = time.time()
    async for ev in cnvs.run(query=QUESTION):
        if not isinstance(ev, dict): continue
        et = ev.get('event','')
        data = ev.get('data') or {}
        if et == 'message':
            c = data.get('content') if isinstance(data, dict) else None
            if c: answer_parts.append(c)
        elif et == 'message_end':
            c = data.get('content') if isinstance(data, dict) else None
            if c: final_message_content = c
        elif et == 'node_finished':
            if isinstance(data, dict):
                cname = data.get("component_name", "")
                if cname == "Reply" or data.get("component_type") == "Message":
                    outputs = data.get("outputs") or {}
                    if isinstance(outputs, dict) and outputs.get("content"):
                        final_message_content = outputs["content"]
    elapsed = time.time() - t0
    answer = final_message_content if final_message_content else "".join(answer_parts)

    print(f'Elapsed: {elapsed:.1f}s')
    print(f'Total length: {len(answer)} chars')
    print()
    print('=== FULL ANSWER ===')
    print(answer)
asyncio.run(go())
